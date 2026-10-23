#!/usr/bin/env python3
import subprocess
import sys

def run_pg_dump(db_name: str, output_file: str) -> None:
    cmd = ['pg_dump', '-Fc', '-b', '-v', '-f', output_file, db_name]
    subprocess.check_call(cmd)

if __name__ == '__main__':
    run_pg_dump('production_db', 'prod_backup.dump')
