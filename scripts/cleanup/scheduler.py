#!/usr/bin/env python3
"""
scheduler.py - cronライクなジョブスケジューラ

Usage:
    python scheduler.py [--config CONFIG_FILE] [--log-file LOG_FILE]

Options:
    --config CONFIG_FILE  : ジョブ定義ファイル（デフォルト: config/jobs/cleanup_jobs.json）
    --log-file LOG_FILE   : ログファイル（デフォルト: logs/scheduler_audit.log）
"""

import argparse
import json
import logging
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# croniter for cron expression parsing
try:
    from croniter import croniter
except ImportError:
    print("Error: croniter is not installed", file=sys.stderr)
    print("Please install it: uv add croniter", file=sys.stderr)
    sys.exit(1)


class CleanupScheduler:
    """軽量スケジューラ（cronライク）"""

    def __init__(self, config_path: Path, log_file: Path, db_path: Path):
        self.config_path = config_path
        self.log_file = log_file
        self.db_path = db_path
        self.jobs: List[Dict[str, Any]] = []
        self.running = True

        # ロギング設定
        self.setup_logging()

        # 設定ファイル読み込み
        self.load_config()

    def setup_logging(self):
        """ロギング設定"""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout),
            ],
        )
        self.logger = logging.getLogger(__name__)

    def load_config(self):
        """ジョブ定義ファイル読み込み"""
        if not self.config_path.exists():
            self.logger.error(f"Config file not found: {self.config_path}")
            sys.exit(1)

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        self.jobs = config.get("jobs", [])
        self.logger.info(f"Loaded {len(self.jobs)} jobs from {self.config_path}")

        # 各ジョブに次回実行時刻を設定
        now = datetime.now()
        for job in self.jobs:
            if job.get("enabled", True):
                schedule = job.get("schedule")
                if schedule:
                    cron = croniter(schedule, now)
                    job["next_run"] = cron.get_next(datetime)
                    self.logger.info(
                        f"Job '{job['name']}' scheduled for {job['next_run']}"
                    )

    def run_job(self, job: Dict[str, Any]):
        """ジョブ実行"""
        job_name = job["name"]
        command = job["command"]
        args = job.get("args", [])
        dry_run = job.get("dry_run", False)

        self.logger.info(f"Running job: {job_name}")

        # コマンド実行
        cmd = [command] + args
        if dry_run:
            cmd.append("--dry-run")

        started_at = datetime.utcnow().isoformat() + "Z"
        exit_code = 0
        error_message = None

        try:
            result = subprocess.run(
                cmd,
                cwd=Path(__file__).parent.parent.parent,  # プロジェクトルート
                capture_output=True,
                text=True,
                timeout=300,  # 5分タイムアウト
            )
            exit_code = result.returncode

            if exit_code == 0:
                self.logger.info(f"Job '{job_name}' completed successfully")
                self.logger.debug(f"stdout: {result.stdout}")
            else:
                error_message = result.stderr
                self.logger.error(
                    f"Job '{job_name}' failed with exit code {exit_code}"
                )
                self.logger.error(f"stderr: {result.stderr}")

        except subprocess.TimeoutExpired:
            exit_code = -1
            error_message = "Timeout (300s)"
            self.logger.error(f"Job '{job_name}' timed out")

        except Exception as e:
            exit_code = -2
            error_message = str(e)
            self.logger.error(f"Job '{job_name}' raised exception: {e}")

        finished_at = datetime.utcnow().isoformat() + "Z"

        # 監査ログDB記録（cleanup_db.shやcleanup_files.shが既に記録するため、ここでは重複しない）
        # ジョブ実行履歴のみを記録する場合は、別テーブルを作成するか、job_nameで区別する
        # 今回はスクリプト側で記録するため、scheduler側では記録しない（または別途記録）

        # 次回実行時刻更新
        schedule = job.get("schedule")
        if schedule:
            now = datetime.now()
            cron = croniter(schedule, now)
            job["next_run"] = cron.get_next(datetime)
            self.logger.info(f"Job '{job_name}' next run: {job['next_run']}")

    def run(self):
        """メインループ"""
        self.logger.info("Scheduler started")

        while self.running:
            now = datetime.now()

            # 実行対象ジョブをチェック
            for job in self.jobs:
                if not job.get("enabled", True):
                    continue

                next_run = job.get("next_run")
                if next_run and now >= next_run:
                    self.run_job(job)

            # 1分間スリープ
            time.sleep(60)

        self.logger.info("Scheduler stopped")

    def stop(self):
        """停止"""
        self.running = False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="Cleanup Job Scheduler")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/jobs/cleanup_jobs.json"),
        help="Job definition file",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("logs/scheduler_audit.log"),
        help="Log file",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("data/ai_secretary.db"),
        help="Database file",
    )

    args = parser.parse_args()

    # プロジェクトルートに移動
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / args.config
    log_file = project_root / args.log_file
    db_path = project_root / args.db

    scheduler = CleanupScheduler(config_path, log_file, db_path)

    try:
        scheduler.run()
    except KeyboardInterrupt:
        scheduler.logger.info("Received SIGINT, stopping...")
        scheduler.stop()


if __name__ == "__main__":
    main()
