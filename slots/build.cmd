@echo off
rem Compila dbfzslots.dll e o teste offline com Zig (toolchain\zig-x86_64-windows-0.16.0).
setlocal
set ROOT=%~dp0
set ZIG=%ROOT%..\toolchain\zig-x86_64-windows-0.16.0\zig.exe
if not exist "%ZIG%" set ZIG=zig
if not exist "%ROOT%out" mkdir "%ROOT%out"
"%ZIG%" cc -target x86_64-windows-gnu -shared -O2 -Wall -o "%ROOT%out\dbfzslots.dll" "%ROOT%src\slots.c" "%ROOT%src\caves.S" || goto :fail
"%ZIG%" cc -target x86_64-windows-gnu -O1 -municode -o "%ROOT%out\offline_test.exe" "%ROOT%tests\offline_test.c" "%ROOT%tests\callsite.S" || goto :fail
echo Compilado: out\dbfzslots.dll, out\offline_test.exe
exit /b 0
:fail
echo Falha na compilacao.
exit /b 1
