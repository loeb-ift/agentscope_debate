"""
EDA (Exploratory Data Analysis) Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class EDADescribeRequest(BaseModel):
    """Request schema for /eda/describe endpoint."""
    
    csv_path: str = Field(..., description="Absolute path to the CSV file to analyze")
    include_cols: Optional[List[str]] = Field(
        None, 
        description="Optional list of column names to include in analysis. If None, analyze all columns."
    )
    sample: Optional[int] = Field(
        None, 
        description="Optional sample size. If provided and dataset has more rows, randomly sample this many rows."
    )
    lang: str = Field(
        "zh", 
        description="Report language. Supported: 'zh' (Chinese), 'en' (English)"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "csv_path": "/data/staging/debate_001/2330.TW.csv",
                "include_cols": ["date", "close", "volume"],
                "sample": 50000,
                "lang": "zh"
            }
        }


class EDAMetadata(BaseModel):
    """Metadata about the generated EDA report."""
    
    rows: int = Field(..., description="Number of rows in the dataset")
    cols: int = Field(..., description="Number of columns in the dataset")
    missing_rate: float = Field(..., description="Overall missing value rate (0.0 to 1.0)")
    generated_at: str = Field(..., description="ISO 8601 timestamp when report was generated")
    engine: str = Field("ydata-profiling", description="EDA engine used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "rows": 1250,
                "cols": 5,
                "missing_rate": 0.01,
                "generated_at": "2023-10-27T10:00:00Z",
                "engine": "ydata-profiling"
            }
        }


class EDADescribeResponse(BaseModel):
    """Response schema for /eda/describe endpoint."""
    
    report_path: str = Field(..., description="Absolute path to the generated HTML report")
    plot_paths: List[str] = Field(
        default_factory=list, 
        description="List of absolute paths to generated plot images (PNG)"
    )
    table_paths: List[str] = Field(
        default_factory=list,
        description="List of absolute paths to generated summary tables (CSV)"
    )
    meta: EDAMetadata = Field(..., description="Metadata about the analysis")
    
    class Config:
        json_schema_extra = {
            "example": {
                "report_path": "/data/reports/debate_001/eda_profile.html",
                "plot_paths": [
                    "/data/plots/debate_001/hist_close.png",
                    "/data/plots/debate_001/corr_matrix.png",
                    "/data/plots/debate_001/box_volume.png"
                ],
                "table_paths": [
                    "/data/tables/debate_001/summary_stats.csv"
                ],
                "meta": {
                    "rows": 1250,
                    "cols": 5,
                    "missing_rate": 0.01,
                    "generated_at": "2023-10-27T10:00:00Z",
                    "engine": "ydata-profiling"
                }
            }
        }


class EDAQuickPlotsRequest(BaseModel):
    """Request schema for /eda/quickplots endpoint (optional, for future use)."""
    
    csv_path: str = Field(..., description="Absolute path to the CSV file")
    tasks: List[str] = Field(
        ..., 
        description="List of plot types to generate. Options: 'hist', 'box', 'scatter', 'corr'"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "csv_path": "/data/staging/debate_001/2330.TW.csv",
                "tasks": ["hist", "box", "scatter"]
            }
        }


class EDAQuickPlotsResponse(BaseModel):
    """Response schema for /eda/quickplots endpoint."""
    
    plot_paths: List[str] = Field(
        default_factory=list,
        description="List of absolute paths to generated plots"
    )
