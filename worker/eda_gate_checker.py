"""
EDA Gate Checker - Validates EDA artifacts quality and completeness.

Implements the gating logic to ensure EDA reports meet minimum quality standards
before being accepted as verified evidence.
"""
import os
from typing import Dict, List, Any
from datetime import datetime, timedelta
from pathlib import Path


class EDAGateChecker:
    """
    Gate checker for EDA artifacts.
    
    Performs quality checks on generated EDA reports, plots, and tables
    to ensure they meet minimum standards for use as evidence.
    """
    
    def __init__(
        self,
        min_rows: int = 30,
        max_age_hours: int = 24,
        require_numeric_cols: bool = True
    ):
        """
        Initialize gate checker.
        
        Args:
            min_rows: Minimum number of rows required in dataset
            max_age_hours: Maximum age of artifacts in hours
            require_numeric_cols: Whether to require at least one numeric column
        """
        self.min_rows = min_rows
        self.max_age_hours = max_age_hours
        self.require_numeric_cols = require_numeric_cols
    
    def check(self, artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute gate checks on EDA artifacts.
        
        Args:
            artifacts: Dictionary with report_path, plot_paths, table_paths, and meta
            
        Returns:
            Dictionary with:
                - passed: bool, whether all checks passed
                - issues: List[str], list of issues found
                - degraded_mode: bool, whether to use degraded mode
                - checks: Dict, detailed check results
        """
        issues = []
        checks = {}
        
        # Extract metadata
        meta = artifacts.get("meta", {})
        report_path = artifacts.get("report_path")
        plot_paths = artifacts.get("plot_paths", [])
        table_paths = artifacts.get("table_paths", [])
        
        # Check 1: File Readability
        file_check = self._check_files_exist(report_path, plot_paths, table_paths)
        checks["files_exist"] = file_check
        if not file_check["passed"]:
            issues.extend(file_check["issues"])
        
        # Check 2: Sample Threshold
        rows = meta.get("rows", 0)
        sample_check = self._check_sample_threshold(rows)
        checks["sample_threshold"] = sample_check
        if not sample_check["passed"]:
            issues.append(sample_check["issue"])
        
        # Check 3: Numeric Columns (if required)
        if self.require_numeric_cols:
            # We infer this from plot_paths - if plots were generated, there must be numeric cols
            numeric_check = self._check_numeric_columns(plot_paths)
            checks["numeric_columns"] = numeric_check
            if not numeric_check["passed"]:
                issues.append(numeric_check["issue"])
        
        # Check 4: Freshness
        generated_at = meta.get("generated_at")
        freshness_check = self._check_freshness(generated_at)
        checks["freshness"] = freshness_check
        if not freshness_check["passed"]:
            issues.append(freshness_check["issue"])
        
        # Determine overall pass/fail
        passed = len(issues) == 0
        degraded_mode = not passed
        
        return {
            "passed": passed,
            "issues": issues,
            "degraded_mode": degraded_mode,
            "checks": checks
        }
    
    def _check_files_exist(
        self,
        report_path: str,
        plot_paths: List[str],
        table_paths: List[str]
    ) -> Dict[str, Any]:
        """Check if all artifact files exist and are readable."""
        issues = []
        
        # Check report
        if not report_path or not os.path.exists(report_path):
            issues.append(f"Report file not found: {report_path}")
        elif not os.access(report_path, os.R_OK):
            issues.append(f"Report file not readable: {report_path}")
        
        # Check plots
        for plot_path in plot_paths:
            if not os.path.exists(plot_path):
                issues.append(f"Plot file not found: {plot_path}")
            elif not os.access(plot_path, os.R_OK):
                issues.append(f"Plot file not readable: {plot_path}")
        
        # Check tables
        for table_path in table_paths:
            if not os.path.exists(table_path):
                issues.append(f"Table file not found: {table_path}")
            elif not os.access(table_path, os.R_OK):
                issues.append(f"Table file not readable: {table_path}")
        
        return {
            "passed": len(issues) == 0,
            "issues": issues
        }
    
    def _check_sample_threshold(self, rows: int) -> Dict[str, Any]:
        """Check if dataset has minimum required rows."""
        passed = rows >= self.min_rows
        
        return {
            "passed": passed,
            "issue": f"樣本數不足：僅有 {rows} 筆，需要至少 {self.min_rows} 筆" if not passed else None,
            "rows": rows,
            "min_rows": self.min_rows
        }
    
    def _check_numeric_columns(self, plot_paths: List[str]) -> Dict[str, Any]:
        """
        Check if dataset has numeric columns.
        
        We infer this from whether plots were generated.
        If no plots, likely no numeric columns.
        """
        has_plots = len(plot_paths) > 0
        
        return {
            "passed": has_plots,
            "issue": "數據集缺少數值欄位，無法生成統計圖表" if not has_plots else None,
            "plot_count": len(plot_paths)
        }
    
    def _check_freshness(self, generated_at: str) -> Dict[str, Any]:
        """Check if artifacts are fresh (within max_age_hours)."""
        if not generated_at:
            return {
                "passed": False,
                "issue": "缺少生成時間戳記"
            }
        
        try:
            # Parse ISO 8601 timestamp
            gen_time = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            now = datetime.now(gen_time.tzinfo)
            age = now - gen_time
            max_age = timedelta(hours=self.max_age_hours)
            
            passed = age <= max_age
            
            return {
                "passed": passed,
                "issue": f"報表過期：生成於 {age.total_seconds() / 3600:.1f} 小時前" if not passed else None,
                "age_hours": age.total_seconds() / 3600,
                "max_age_hours": self.max_age_hours
            }
        except Exception as e:
            return {
                "passed": False,
                "issue": f"無效的時間戳記格式: {generated_at}"
            }
    
    def get_degradation_message(self, issues: List[str]) -> str:
        """
        Generate a user-friendly degradation message.
        
        Args:
            issues: List of issues from gate check
            
        Returns:
            Formatted message explaining why EDA failed and suggesting alternatives
        """
        if not issues:
            return ""
        
        message = "⚠️ EDA 自動分析未能通過品質檢查，原因如下：\n"
        for i, issue in enumerate(issues, 1):
            message += f"{i}. {issue}\n"
        
        message += "\n建議：本輪將採用定性描述，不提供詳細量化分析。"
        
        return message
