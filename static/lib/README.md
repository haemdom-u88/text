说明：将 echarts.min.js 放置到此目录以在离线或被浏览器策略阻断时保证本地加载。

推荐下载方法：

1) 使用浏览器直接访问并保存：
   https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js

2) 使用 curl（Windows WSL 或类 Unix）：
   curl -L -o static/lib/echarts.min.js "https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"

3) 使用 PowerShell (Windows)：
   iwr -Uri "https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js" -OutFile "static/lib/echarts.min.js"

注意：下载后确保文件路径为 `static/lib/echarts.min.js`，并重启 Flask 服务或清除浏览器缓存以使本地文件生效。