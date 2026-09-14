
# 引数なしの `just` でレシピ一覧を表示
default:
    @just --list

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

lab:
    cd robotics-hub; npm run dev:m5