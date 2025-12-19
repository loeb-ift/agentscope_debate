"""
EDA Service Layer - Handles data analysis logic using ydata-profiling and matplotlib.
"""
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server environments
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from ydata_profiling import ProfileReport


class EDAService:
    """Service for generating EDA reports and visualizations."""
    
    def __init__(self, base_data_dir: str = "/data"):
        """
        Initialize EDA service.
        
        Args:
            base_data_dir: Base directory for data storage (default: /data)
        """
        self.base_data_dir = Path(base_data_dir)
        self.reports_dir = self.base_data_dir / "reports"
        self.plots_dir = self.base_data_dir / "plots"
        self.tables_dir = self.base_data_dir / "tables"
        
    def _ensure_dirs(self, debate_id: str) -> Tuple[Path, Path, Path]:
        """
        Ensure output directories exist for a given debate.
        
        Args:
            debate_id: Unique debate identifier
            
        Returns:
            Tuple of (report_dir, plot_dir, table_dir)
        """
        report_dir = self.reports_dir / debate_id
        plot_dir = self.plots_dir / debate_id
        table_dir = self.tables_dir / debate_id
        
        report_dir.mkdir(parents=True, exist_ok=True)
        plot_dir.mkdir(parents=True, exist_ok=True)
        table_dir.mkdir(parents=True, exist_ok=True)
        
        return report_dir, plot_dir, table_dir
    
    def load_csv(
        self, 
        csv_path: str, 
        include_cols: Optional[List[str]] = None,
        sample: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Load CSV file with optional column filtering and sampling.
        
        Args:
            csv_path: Path to CSV file
            include_cols: Optional list of columns to include
            sample: Optional sample size
            
        Returns:
            Loaded DataFrame
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If include_cols contains invalid column names
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Load CSV
        df = pd.read_csv(csv_path)
        
        # Calculate Technical Indicators if pandas_ta is available
        try:
            import pandas_ta as ta
            # Ensure index is datetime for TA
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                
                # Simple Moving Averages
                df['SMA_20'] = ta.sma(df['close'], length=20)
                df['SMA_60'] = ta.sma(df['close'], length=60)
                
                # RSI
                df['RSI_14'] = ta.rsi(df['close'], length=14)
                
                # MACD
                macd = ta.macd(df['close'])
                if macd is not None:
                    df = pd.concat([df, macd], axis=1)
                
                # Bollinger Bands
                bbands = ta.bbands(df['close'])
                if bbands is not None:
                    df = pd.concat([df, bbands], axis=1)
                
                # Reset index to keep date as column
                df.reset_index(inplace=True)
                
        except ImportError:
            pass  # Skip if pandas_ta not installed
        except Exception as e:
            print(f"Error calculating technical indicators: {e}")

        # Filter columns if specified
        if include_cols:
            # Only filter columns that actually exist in the dataframe
            # This allows requested columns to be optional (e.g. financial data might be missing)
            available_cols = [c for c in include_cols if c in df.columns]
            
            # If we calculated technical indicators, include them automatically
            ta_cols = [c for c in df.columns if any(x in c for x in ['SMA', 'RSI', 'MACD', 'BBL', 'BBM', 'BBU'])]
            
            final_cols = list(set(available_cols + ta_cols))
            df = df[final_cols]
        
        # Sample if specified and dataset is large enough
        if sample and len(df) > sample:
            df = df.sample(n=sample, random_state=42)
        
        return df
    
    def generate_profile_report(
        self,
        df: pd.DataFrame,
        output_path: str,
        title: str = "EDA Profile Report",
        lang: str = "zh"
    ) -> str:
        """
        Generate ydata-profiling HTML report.
        
        Args:
            df: DataFrame to analyze
            output_path: Path to save HTML report
            title: Report title
            lang: Report language ('zh' or 'en')
            
        Returns:
            Path to generated HTML report
        """
        # Configure profiling
        profile = ProfileReport(
            df,
            title=title,
            explorative=True,
            minimal=False,  # Full report
            # Note: ydata-profiling doesn't have built-in Chinese support
            # We'll use English and add Chinese annotations in Chairman summary
        )
        
        # Generate and save report
        profile.to_file(output_path)
        
        return output_path
    
    def generate_basic_plots(
        self,
        df: pd.DataFrame,
        output_dir: Path,
        prefix: str = ""
    ) -> List[str]:
        """
        Generate basic statistical plots (histogram, correlation matrix, boxplot).
        
        Args:
            df: DataFrame to visualize
            output_dir: Directory to save plots
            prefix: Optional filename prefix
            
        Returns:
            List of paths to generated plot files
        """
        plot_paths = []
        
        # Identify numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        if not numeric_cols:
            # No numeric columns, skip plotting
            return plot_paths
        
        # Set Chinese font support (if available)
        try:
            plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
        except:
            pass  # Use default font if Chinese fonts not available
        
        # 1. Histograms for numeric columns (max 6 columns to avoid clutter)
        if numeric_cols:
            n_cols = min(len(numeric_cols), 6)
            fig, axes = plt.subplots(2, 3, figsize=(15, 10))
            axes = axes.flatten()
            
            for i, col in enumerate(numeric_cols[:n_cols]):
                df[col].hist(bins=30, ax=axes[i], edgecolor='black')
                axes[i].set_title(f'{col} Distribution')
                axes[i].set_xlabel(col)
                axes[i].set_ylabel('Frequency')
            
            # Hide unused subplots
            for i in range(n_cols, 6):
                axes[i].axis('off')
            
            plt.tight_layout()
            hist_path = output_dir / f"{prefix}hist_distributions.png"
            plt.savefig(hist_path, dpi=100, bbox_inches='tight')
            plt.close()
            plot_paths.append(str(hist_path))
        
        # 2. Correlation Matrix (if multiple numeric columns)
        if len(numeric_cols) > 1:
            fig, ax = plt.subplots(figsize=(10, 8))
            corr_matrix = df[numeric_cols].corr()
            sns.heatmap(
                corr_matrix, 
                annot=True, 
                fmt='.2f', 
                cmap='coolwarm', 
                center=0,
                ax=ax,
                square=True
            )
            ax.set_title('Correlation Matrix')
            plt.tight_layout()
            corr_path = output_dir / f"{prefix}corr_matrix.png"
            plt.savefig(corr_path, dpi=100, bbox_inches='tight')
            plt.close()
            plot_paths.append(str(corr_path))
        
        # 3. Boxplots for numeric columns (max 6)
        if numeric_cols:
            n_cols = min(len(numeric_cols), 6)
            fig, axes = plt.subplots(2, 3, figsize=(15, 10))
            axes = axes.flatten()
            
            for i, col in enumerate(numeric_cols[:n_cols]):
                df.boxplot(column=col, ax=axes[i])
                axes[i].set_title(f'{col} Boxplot')
                axes[i].set_ylabel(col)
            
            # Hide unused subplots
            for i in range(n_cols, 6):
                axes[i].axis('off')
            
            plt.tight_layout()
            box_path = output_dir / f"{prefix}box_plots.png"
            plt.savefig(box_path, dpi=100, bbox_inches='tight')
            plt.close()
            plot_paths.append(str(box_path))
        
        return plot_paths
    
    def extract_summary_stats(
        self,
        df: pd.DataFrame,
        output_path: str
    ) -> str:
        """
        Extract and save summary statistics to CSV.
        
        Args:
            df: DataFrame to summarize
            output_path: Path to save summary CSV
            
        Returns:
            Path to generated CSV file
        """
        # Get summary statistics
        summary = df.describe(include='all').transpose()
        
        # Add additional info
        summary['dtype'] = df.dtypes
        summary['missing_count'] = df.isnull().sum()
        summary['missing_rate'] = df.isnull().sum() / len(df)
        
        # Save to CSV
        summary.to_csv(output_path)
        
        return output_path
    
    def analyze(
        self,
        csv_path: str,
        debate_id: str,
        include_cols: Optional[List[str]] = None,
        sample: Optional[int] = None,
        lang: str = "zh"
    ) -> Dict[str, Any]:
        """
        Main analysis method - orchestrates the full EDA pipeline.
        
        Args:
            csv_path: Path to CSV file
            debate_id: Unique debate identifier
            include_cols: Optional column filter
            sample: Optional sample size
            lang: Report language
            
        Returns:
            Dictionary with report_path, plot_paths, table_paths, and metadata
        """
        # Ensure output directories exist
        report_dir, plot_dir, table_dir = self._ensure_dirs(debate_id)
        
        # Load data
        df = self.load_csv(csv_path, include_cols, sample)
        
        # Generate profile report
        report_path = report_dir / "eda_profile.html"
        self.generate_profile_report(
            df, 
            str(report_path),
            title=f"EDA Report - {debate_id}",
            lang=lang
        )
        
        # Generate basic plots
        plot_paths = self.generate_basic_plots(df, plot_dir, prefix="")
        
        # Extract summary stats
        table_path = table_dir / "summary_stats.csv"
        self.extract_summary_stats(df, str(table_path))
        table_paths = [str(table_path)]
        
        # Calculate metadata
        missing_rate = df.isnull().sum().sum() / (df.shape[0] * df.shape[1])
        
        metadata = {
            "rows": len(df),
            "cols": len(df.columns),
            "missing_rate": round(missing_rate, 4),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "engine": "ydata-profiling"
        }
        
        return {
            "report_path": str(report_path),
            "plot_paths": plot_paths,
            "table_paths": table_paths,
            "meta": metadata
        }
