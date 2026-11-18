@echo off
rem Klik dua kali untuk memasang paket pembaruan (rilis_*.tgz / .zip).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1"
