
# 引数なしの `just` でレシピ一覧を表示
default:
    @just --list

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

lab:
    cd robotics-hub; npm run dev:m5

# ATOM / CoreS3 の USB で Hub を開く監視を、サインイン時のスタートアップへ登録する
usb-watch-on:
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File link/host/install_usb_watch.ps1

# サインイン時の USB 監視を外す。起動済みの Hub は止めない
usb-watch-off:
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File link/host/uninstall_usb_watch.ps1