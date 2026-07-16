#!/usr/bin/env python3
"""
Optimized CLI Tool for Fast File Ingestion
==========================================

This script provides an alternate, high-performance CLI interface for ingesting
data files into the database. It includes several optimizations over the web-based
ingestion endpoint:

- Chunked CSV processing to minimize memory usage
- SQLite WAL mode for improved write performance
- Visual progress tracking with tqdm
- Comprehensive logging
- Dry-run mode for validation
- Resume capability with state tracking
- Configurable concurrency and batch sizes

Usage:
    python cli_ingest.py <csv_file_path> [options]

Examples:
    # Basic ingestion
    python cli_ingest.py "Transparency dataset.csv"
    
    # With custom workers and chunk size
    python cli_ingest.py "data.csv" --workers 20 --chunk-size 2000
    
    # Dry run to preview
    python cli_ingest.py "data.csv" --dry-run
    
    # Verbose logging
    python cli_ingest.py "data.csv" --verbose
    
    # Resume from previous run
    python cli_ingest.py "data.csv" --resume
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
import sqlite3
import pandas as pd
from typing import Dict, List, Tuple, Optional
import concurrent.futures
from dataclasses import dataclass

# Try to import tqdm for progress bars
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("Warning: tqdm not installed. Install with 'pip install tqdm' for progress bars.")

# Add src to path to import local modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database import init_db, get_connection, DB_FILE
from src.auth import get_password_hash


@dataclass
class IngestionStats:
    """Statistics for ingestion process"""
    total_rows: int = 0
    users_created: int = 0
    users_updated: int = 0
    reports_added: int = 0
    errors: int = 0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def duration(self) -> float:
        """Get duration in seconds"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    def format_summary(self) -> str:
        """Format a summary string"""
        duration = self.duration()
        rows_per_sec = self.total_rows / duration if duration > 0 else 0
        
        return f"""
╔══════════════════════════════════════════════════════════════╗
║                  INGESTION COMPLETE                          ║
╠══════════════════════════════════════════════════════════════╣
║  Total Rows Processed:  {self.total_rows:>10}                      ║
║  Users Created:         {self.users_created:>10}                      ║
║  Users Updated:         {self.users_updated:>10}                      ║
║  Reports Added:         {self.reports_added:>10}                      ║
║  Errors:                {self.errors:>10}                      ║
║  Duration:              {duration:>10.2f}s                    ║
║  Processing Speed:      {rows_per_sec:>10.2f} rows/sec            ║
╚═════════════════════════════════════════════════════════ ═════╝
"""


class CLIIngestion:
    """Main CLI ingestion handler"""
    
    def __init__(self, args):
        self.args = args
        self.stats = IngestionStats()
        self.logger = self._setup_logging()
        self.state_file = Path("ingestion_state.txt")
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        log_level = logging.DEBUG if self.args.verbose else logging.INFO
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Setup logger
        logger = logging.getLogger('cli_ingest')
        logger.setLevel(log_level)
        
        # File handler
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fh = logging.FileHandler(log_dir / f"ingestion_{timestamp}.log")
        fh.setLevel(log_level)
        fh.setFormatter(logging.Formatter(log_format))
        logger.addHandler(fh)
        
        # Console handler (only if verbose)
        if self.args.verbose:
            ch = logging.StreamHandler()
            ch.setLevel(log_level)
            ch.setFormatter(logging.Formatter(log_format))
            logger.addHandler(ch)
        
        return logger
    
    def _enable_wal_mode(self):
        """Enable Write-Ahead Logging mode for better performance"""
        try:
            conn = get_connection()
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA cache_size=-64000;")  # 64MB cache
            conn.execute("PRAGMA temp_store=MEMORY;")
            conn.close()
            self.logger.info("Enabled SQLite WAL mode and performance optimizations")
        except Exception as e:
            self.logger.warning(f"Could not enable WAL mode: {e}")
    
    def _save_state(self, processed_rows: int):
        """Save current state for resume capability"""
        try:
            with open(self.state_file, 'w') as f:
                f.write(str(processed_rows))
        except Exception as e:
            self.logger.warning(f"Could not save state: {e}")
    
    def _load_state(self) -> int:
        """Load previous state"""
        if not self.args.resume or not self.state_file.exists():
            return 0
        try:
            with open(self.state_file, 'r') as f:
                rows = int(f.read().strip())
                self.logger.info(f"Resuming from row {rows}")
                return rows
        except Exception as e:
            self.logger.warning(f"Could not load state: {e}")
            return 0
    
    def _generate_password(self, name: str, dob: str) -> str:
        """Generate password from name and DOB"""
        try:
            first_four = name[:4].lower().replace(" ", "")
            year = dob.split("-")[0]
            return f"{first_four}{year}"
        except:
            return "pass1234"
    
    def _process_row(self, row: Dict) -> Dict:
        """Process a single row (CPU-intensive hashing)"""
        try:
            mobile = str(row['mobile_number'])
            name = row.get('name', 'Unknown')
            dob = row.get('date_of_birth', '2000-01-01')
            
            password_plain = self._generate_password(name, dob)
            password_hash = get_password_hash(password_plain)
            
            user_data = {
                "username": mobile,
                "password_hash": password_hash,
                "role": "user",
                "full_name": name,
                "mobile_number": mobile,
                "email": row.get('email', ''),
                "aadhaar_number": str(row.get('aadhaar_number_synthetic', '')),
                "age": int(row.get('age', 0)),
                "sex": row.get('sex', 'Other'),
                "date_of_birth": dob
            }
            
            report_data = {
                "category": row.get('category', 'General'),
                "location": row.get('country', 'India'),
                "description": f"Application for {row.get('category')} in {row.get('sector')} sector.",
                "tags": row.get('system_type', ''),
                "sector": row.get('sector', ''),
                "affected_group": row.get('affected_group', ''),
                "appeal_available": row.get('appeal_available', 'No'),
                "status": row.get('decision_outcome', 'Pending'),
                "rejection_reason": row.get('reason_given') if row.get('decision_outcome') == 'Rejected' else None,
                "timestamp": datetime.now().isoformat(),
                "_username": mobile
            }
            
            return {"success": True, "user": user_data, "report": report_data}
        except Exception as e:
            self.logger.error(f"Error processing row: {e}")
            return {"success": False, "error": str(e)}
    
    def _bulk_insert(self, users_dict: Dict, reports_list: List[Dict]) -> Tuple[int, int]:
        """Perform bulk insert into database"""
        if self.args.dry_run:
            self.logger.info(f"[DRY RUN] Would insert {len(users_dict)} users and {len(reports_list)} reports")
            return len(users_dict), len(reports_list)
        
        conn = get_connection()
        c = conn.cursor()
        
        try:
            c.execute("BEGIN TRANSACTION")
            
            # 1. UPSERT Users
            user_list = list(users_dict.values())
            users_created = 0
            users_updated = 0
            
            if user_list:
                user_tuples = [(
                    u['username'], u['password_hash'], u['role'], u['full_name'],
                    u['mobile_number'], u['email'], u['aadhaar_number'],
                    u['age'], u['sex'], u['date_of_birth']
                ) for u in user_list]
                
                # Check existing users
                c.execute("SELECT username FROM users WHERE username IN ({})".format(
                    ','.join('?' * len(user_list))
                ), [u['username'] for u in user_list])
                existing_users = set(row[0] for row in c.fetchall())
                
                c.executemany('''
                    INSERT INTO users (username, password_hash, role, full_name, mobile_number, 
                                     email, aadhaar_number, age, sex, date_of_birth)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(username) DO UPDATE SET
                    password_hash=excluded.password_hash,
                    full_name=excluded.full_name,
                    mobile_number=excluded.mobile_number,
                    email=excluded.email,
                    aadhaar_number=excluded.aadhaar_number,
                    age=excluded.age,
                    sex=excluded.sex,
                    date_of_birth=excluded.date_of_birth
                ''', user_tuples)
                
                users_created = len(user_list) - len(existing_users)
                users_updated = len(existing_users)
            
            # 2. Get User IDs map
            c.execute("SELECT username, id FROM users")
            user_map = {row[0]: row[1] for row in c.fetchall()}
            
            # 3. Insert Reports
            final_reports = []
            for r in reports_list:
                uid = user_map.get(r['_username'])
                if uid:
                    final_reports.append((
                        r['category'], r['location'], r['description'], r['tags'],
                        r['timestamp'], r['status'], uid, r['sector'],
                        r['affected_group'], r['appeal_available'], r['rejection_reason']
                    ))
            
            if final_reports:
                c.executemany('''
                    INSERT INTO reports (category, location, description, tags, timestamp, 
                                       status, user_id, sector, affected_group, 
                                       appeal_available, rejection_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', final_reports)
            
            conn.commit()
            self.logger.info(f"Committed batch: {users_created} new users, {users_updated} updated, {len(final_reports)} reports")
            
            return users_created, users_updated
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Error during bulk insert: {e}")
            raise e
        finally:
            conn.close()
    
    def process_chunk(self, chunk_df: pd.DataFrame, chunk_idx: int) -> Dict:
        """Process a chunk of data"""
        records = chunk_df.to_dict('records')
        users_dict = {}
        reports_list = []
        
        # Phase 1: CPU Work (Password Hashing) with threading
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.args.workers) as executor:
            futures = [executor.submit(self._process_row, row) for row in records]
            
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result["success"]:
                    u = result["user"]
                    r = result["report"]
                    users_dict[u['username']] = u
                    reports_list.append(r)
                else:
                    self.stats.errors += 1
        
        # Phase 2: DB Work (Bulk Insert)
        if users_dict or reports_list:
            users_created, users_updated = self._bulk_insert(users_dict, reports_list)
            self.stats.users_created += users_created
            self.stats.users_updated += users_updated
            self.stats.reports_added += len(reports_list)
        
        return {
            "processed": len(records),
            "users": len(users_dict),
            "reports": len(reports_list)
        }
    
    def run(self):
        """Main execution method"""
        self.logger.info(f"Starting CLI ingestion from: {self.args.csv_file}")
        print(f"\n>>> Starting Fast CLI Ingestion")
        print(f"File: {self.args.csv_file}")
        print(f"Workers: {self.args.workers}")
        print(f"Chunk Size: {self.args.chunk_size}")
        if self.args.dry_run:
            print(f"DRY RUN MODE - No data will be written")
        print()
        
        # Validate file exists
        if not os.path.exists(self.args.csv_file):
            print(f"ERROR: File not found: {self.args.csv_file}")
            return 1
        
        # Initialize database
        if not self.args.dry_run:
            init_db()
            self._enable_wal_mode()
        
        self.stats.start_time = time.time()
        skip_rows = self._load_state() if self.args.resume else 0
        
        try:
            # Get total rows for progress bar
            total_rows = sum(1 for _ in open(self.args.csv_file)) - 1  # Exclude header
            self.stats.total_rows = total_rows - skip_rows
            
            self.logger.info(f"Processing {self.stats.total_rows} rows (skipping {skip_rows})")
            
            # Process CSV in chunks
            if HAS_TQDM:
                pbar = tqdm(total=self.stats.total_rows, desc="Ingesting", unit="rows")
            
            chunk_idx = 0
            for chunk in pd.read_csv(self.args.csv_file, chunksize=self.args.chunk_size, skiprows=range(1, skip_rows + 1)):
                result = self.process_chunk(chunk, chunk_idx)
                
                if HAS_TQDM:
                    pbar.update(result['processed'])
                else:
                    progress = ((chunk_idx + 1) * self.args.chunk_size)
                    percent = min(100, (progress / self.stats.total_rows) * 100)
                    print(f"Progress: {percent:.1f}% ({progress}/{self.stats.total_rows} rows)")
                
                # Save state periodically
                if not self.args.dry_run and chunk_idx % 5 == 0:
                    self._save_state(skip_rows + ((chunk_idx + 1) * self.args.chunk_size))
                
                chunk_idx += 1
            
            if HAS_TQDM:
                pbar.close()
            
            self.stats.end_time = time.time()
            
            # Clean up state file on success
            if not self.args.dry_run and self.state_file.exists():
                self.state_file.unlink()
            
            # Print summary
            print(self.stats.format_summary())
            
            self.logger.info("Ingestion completed successfully")
            return 0
            
        except KeyboardInterrupt:
            print("\n>>> Ingestion interrupted by user")
            self.logger.warning("Ingestion interrupted by user")
            print(f"Progress saved. Run with --resume to continue from where you left off.")
            return 130
        except Exception as e:
            print(f"\nERROR during ingestion: {e}")
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            return 1


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Fast CLI tool for data ingestion into the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Transparency dataset.csv"
  %(prog)s "data.csv" --workers 20 --chunk-size 2000
  %(prog)s "data.csv" --dry-run --verbose
  %(prog)s "data.csv" --resume
        """
    )
    
    parser.add_argument(
        'csv_file',
        help='Path to the CSV file to ingest'
    )
    
    parser.add_argument(
        '-w', '--workers',
        type=int,
        default=10,
        help='Number of worker threads for password hashing (default: 10)'
    )
    
    parser.add_argument(
        '-c', '--chunk-size',
        type=int,
        default=1000,
        help='Number of rows to process per chunk (default: 1000)'
    )
    
    parser.add_argument(
        '-d', '--dry-run',
        action='store_true',
        help='Perform a dry run without writing to database'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging to console'
    )
    
    parser.add_argument(
        '-r', '--resume',
        action='store_true',
        help='Resume from previous interrupted run'
    )
    
    args = parser.parse_args()
    
    # Run ingestion
    ingestion = CLIIngestion(args)
    exit_code = ingestion.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
