"""
Automated EDA (Exploratory Data Analysis) Engine

Implements sightingdata.com principles:
1. Data Inspection (Nulls, Types)
2. Distribution Analysis (Mean, Median, StdDev)
3. Outlier Detection (Z-Score / IQR)
4. Correlation Analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

class EDAEngine:
    def __init__(self, data: pd.DataFrame):
        self.df = data

    def run_full_eda(self) -> Dict[str, Any]:
        """執行完整 EDA 流程"""
        if self.df.empty:
            return {"error": "Empty dataset"}

        return {
            "data_quality": self._check_quality(),
            "descriptive_stats": self._get_descriptive_stats(),
            "outliers": self._detect_outliers(),
            "correlations": self._get_correlations()
        }

    def _check_quality(self) -> Dict[str, Any]:
        """Step 1: 數據品質檢查 (Missing Values)"""
        null_counts = self.df.isnull().sum().to_dict()
        data_types = self.df.dtypes.astype(str).to_dict()
        return {
            "missing_values": null_counts,
            "data_types": data_types,
            "total_rows": len(self.df)
        }

    def _get_descriptive_stats(self) -> Dict[str, Any]:
        """Step 2: 分佈分析"""
        stats = self.df.describe().to_dict()
        skewness = self.df.skew(numeric_only=True).to_dict()
        return {
            "summary": stats,
            "skewness": skewness
        }

    def _detect_outliers(self) -> Dict[str, Any]:
        """Step 3: 異常值檢測 (IQR Method)"""
        outliers_report = {}
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            Q1 = self.df[col].quantile(0.25)
            Q3 = self.df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outliers = self.df[(self.df[col] < lower_bound) | (self.df[col] > upper_bound)][col].tolist()
            if outliers:
                outliers_report[col] = {
                    "count": len(outliers),
                    "values_sample": outliers[:5],
                    "bounds": [round(lower_bound, 2), round(upper_bound, 2)]
                }
        return outliers_report

    def _get_correlations(self) -> Dict[str, Any]:
        """Step 4: 相關性分析"""
        corr_matrix = self.df.corr(numeric_only=True).to_dict()
        return corr_matrix

def run_eda_pipeline(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agent 調用的 EDA 入口點"""
    df = pd.DataFrame(data)
    engine = EDAEngine(df)
    return engine.run_full_eda()
