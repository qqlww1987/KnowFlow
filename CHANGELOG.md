# KnowFlow 更新日志


## [v0.4.0] - 2025-05-29（兼容 RAGFlow v0.19.0）
### 新增
- 支持更多的文件格式，包含 doc、ppt、docx、url、excel 等文件格式，具体格式如下：

    ".123", ".602", ".abw", ".bib", ".bmp", ".cdr", ".cgm", ".cmx", ".csv", ".cwk", ".dbf", ".dif", 
    ".doc", ".docm", ".docx", ".dot", ".dotm", ".dotx", ".dxf", ".emf", ".eps", ".epub", ".fodg", 
    ".fodp", ".fods", ".fodt", ".fopd", ".gif", ".htm", ".html", ".hwp", ".jpeg", ".jpg", ".key", 
    ".ltx", ".lwp", ".mcw", ".met", ".mml", ".mw", ".numbers", ".odd", ".odg", ".odm", ".odp", 
    ".ods", ".odt", ".otg", ".oth", ".otp", ".ots", ".ott", ".pages", ".pbm", ".pcd", ".pct", 
    ".pcx", ".pdb", ".pgm", ".png", ".pot", ".potm", ".potx", ".ppm", ".pps", ".ppt", ".pptm", 
    ".pptx", ".psd", ".psw", ".pub", ".pwp", ".pxl", ".ras", ".rtf", ".sda", ".sdc", ".sdd", 
    ".sdp", ".sdw", ".sgl", ".slk", ".smf", ".stc", ".std", ".sti", ".stw", ".svg", ".svm", 
    ".swf", ".sxc", ".sxd", ".sxg", ".sxi", ".sxm", ".sxw", ".tga", ".tif", ".tiff", ".txt", 
    ".uof", ".uop", ".uos", ".uot", ".vdx", ".vor", ".vsd", ".vsdm", ".vsdx", ".wb2", ".wk1", 
    ".wks", ".wmf", ".wpd", ".wpg", ".wps", ".xbm", ".xhtml", ".xls", ".xlsb", ".xlsm", ".xlsx", 
    ".xlt", ".xltm", ".xltx", ".xlw", ".xml", ".xpm", ".zabw" 

- 简化配置流程，避免配置错误导致链接失败


## [v0.3.0] - 2025-05-02（兼容 RAGFlow v0.18.0）
### 新增
- 开源 KnowFlow 前端 dist 产物
- 移除了向量模型配置，默认为最后更新的向量模型
- 适配 RAGFlow v0.18.0


## [v0.2.0] - 2025-04-24（仅支持源码，镜像包尚未构建）
### 新增
- 适配 RAGFlow Plus 的知识库管理
- 支持自定义 chunk 以及坐标回溯
- 支持企业微信三方接入


## [v0.1.2] - 2025-04-17
### 新增
- 图文回答支持在前端页面一键解析，无需复杂配置

## [v0.1.1] - 2025-04-11
### 新增
- 回答结果支持图片展示

## [v0.1.0] - 2025-04-10
### 新增
- 用户后台管理系统（用户管理、团队管理、模型配置管理）
