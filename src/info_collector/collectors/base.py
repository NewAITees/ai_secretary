"""
情報収集器の基底クラス

設計ドキュメント: plan/P7_INFO_COLLECTOR_PLAN.md
"""

from abc import ABC, abstractmethod
from typing import List
from ..models import CollectedInfo


class BaseCollector(ABC):
    """情報収集器の抽象基底クラス"""

    @abstractmethod
    def collect(self, **kwargs) -> List[CollectedInfo]:
        """
        情報を収集

        Returns:
            収集した情報のリスト
        """
        pass
