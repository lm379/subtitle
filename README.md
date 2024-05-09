## 说明
本项目代码来自大佬[chen310](https://github.com/chen310)的replit库  
当你看见本项目时，我默认你已经安装好了BilibiliPotplayer插件，如何安装请访问[原项目](https://github.com/chen310/BilibiliPotPlayer)  
## 实现功能
为项目[BilibiliPotPlayer](https://github.com/chen310/BilibiliPotPlayer)实现弹幕功能  
由于replit失效，vercel部署后不绑定自定义域名在境内无法访问， 因此可以通过本项目自行部署弹幕代理服务  
## 部署教程
### 本地或服务器部署
1. 安装Python3  
>   如何安装请自行移步[这里](https://www.runoob.com/python3/python3-install.html)
2. 安装依赖  
`pip3 install -r requirements.txt`
3. 运行
```bash
python3 main.py
```
4. 访问http://127.0.0.1:9999/或者http://{ip}:9999/ 出现success即可  
5. 修改Bilibili_Config.json中下面server字段为你的代理地址  
修改前：
```
 "server": "https://subtitle.chen310.repl.co"
```
修改后：
```
 "server": "http://127.0.0.1:9999"
```
6. 重启Potplayer  
<!-- ### 部署到codesanbox
1. fork本项目
2. 使用github登录[codesanbox](https://codesandbox.io/)
3. 创建项目，选择刚刚fork的项目  
4. 配置环境变量  
>   在codesanbox中配置环境变量请移步[这里](https://codesandbox.io/docs/configuration#environment-variables) -->
