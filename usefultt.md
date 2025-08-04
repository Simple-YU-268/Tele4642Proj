cd Tele4642Proj
ryu-manager hotel_wifi_controller.py
sudo python3 mininettopo.py
python3 flask_room_auth.py

h1 iperf -s &
router iperf -c h1 -b 100M -t 60






网页F12进控制台
showStep('plan-step')
showStep('payment-step')
showStep('device-step')
showStep('success-step')
这样就能单独看到和编辑后续页面的代码效果


checkout	签出 / 切换	切换到指定分支或版本（可带 -b 创建新分支）	git checkout -b dev
branch	分支管理	查看、创建或删除分支	git branch -a
add	添加	将修改加入暂存区（为下一次提交准备）	git add .
commit	提交	将暂存区内容提交到当前分支的历史记录	git commit -m "说明"
push	推送	将本地分支的提交上传到远程仓库	git push origin dev
pull	拉取	从远程仓库获取最新版本并自动合并到当前分支	git pull origin main
fetch	抓取	从远程获取最新版本，但不自动合并，只是更新远程引用	git fetch origin
merge	合并	将指定分支的更改合并到当前分支	git merge dev
rebase	变基	将当前分支的提交“重新应用”在目标分支之上，保持历史更线性	git rebase main
clone	克隆	将远程仓库完整复制到本地	git clone <url>
status	状态	查看工作区、暂存区的改动情况	git status
log	日志	查看提交历史记录	git log --oneline
