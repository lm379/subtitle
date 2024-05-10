#!/bin/bash

echo "开始安装依赖"
pip3 install -r requirements.txt
echo "依赖安装完成"

echo "开始启动项目"
nohup python3 main.py &
echo "项目已启动"

if [ ! -f app/cf_zero_status.txt ]
then
    cd app
    touch cf_zero_status.txt
    echo "0" > cf_zero_status.txt
    cd ..
fi
CF_ZERO_STATUS=$(cat app/cf_zero_status.txt)
if [ ! -z $CF_ZERO_TOKEN ] && [ $CF_ZERO_STATUS != 1 ]
then
    echo "开始Cloudflare Zero Trust部署"
    if [ ! -f app/cloudflared ]
    then
        wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O app/cloudflared
        chmod +x app/cloudflared
    fi
    cd app/
    ./cloudflared service install $CF_ZERO_TOKEN
    echo "1" > cf_zero_status.txt
    echo "Cloudflare Zero Trust部署完成"
elif [ $CF_ZERO_STATUS == 1 ]
then
    echo "Cloudflare Zero Trust已部署，跳过部署"
else
    echo "未找到Cloudflare Zero Trust的API Token，跳过部署"
fi
