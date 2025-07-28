@echo off
scrcpy.exe --tcpip=192.168.1.22:3577 --pause-on-exit=if-error %*
