@echo off
rem Windows wrapper for manage.sh — double-click or run: manage.bat <command>
rem Usage examples:
rem   manage.bat setup     start containers + seed all data
rem   manage.bat seed      re-seed everything
rem   manage.bat counts    show row counts for all sources
rem   manage.bat help      list all commands
bash "%~dp0manage.sh" %*
