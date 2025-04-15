# 【集成文档】大疆 Flutter SDK 集成文档  

1. SDK 功能清单2. 3. SDK 预置事件与预置属性3. 集成神策分析 SDK Flutter 插件3.1. 引入插件  
4. Flutter 插件初始化4.1. 获取项目数据接收地址4.2. 初始化 SDK4.2.1. init() 方法参数说明5. 配置 Scheme5.1. 获取项目 Scheme5.2. App 中添加 Scheme  
6. SDK 基本配置6.1. 用户关联6.2. 设置事件公共属性6.3. 记录激活事件6.4. 代码埋点追踪事件7. 调试查看事件信息  

神策 Flutter SDK Flutter 插件 universal_statistics_flutter_plugin，封装了神策 Android 和 iOS SDK 常用 API，使用此插件，可以完成代码埋点的统计和上报。  

# 1. SDK 功能清单  

<html><body><table><tr><td>一级功能</td><td>二级功能</td><td>具体功能／描述</td></tr><tr><td rowspan="4">标识用户</td><td rowspan="2">自动标识匿名用户</td><td>自动使用设备ID标识匿名用户</td></tr><tr><td>支持替换为自定义的匿名ID</td></tr><tr><td>标识登录用户</td><td>使用登录ID标识登录用户</td></tr><tr><td>设置用户属性</td><td></td></tr><tr><td rowspan="8">采集数据</td><td rowspan="2">自动采集设备信息</td><td>自动采集默认的设备信息，屏幕宽高、系统版本号等</td></tr><tr><td>支持自动采集屏幕方向</td></tr><tr><td rowspan="2">全埋点</td><td>支持自动采集经纬度信息</td></tr><tr><td>App启动</td></tr><tr><td rowspan="2">公共属性</td><td>App退出</td></tr><tr><td>静态公共属性 清除公共属性</td></tr><tr><td rowspan="2">自定义埋点</td><td>采集激活（安装）事件</td></tr><tr><td>统计事件时长</td></tr><tr><td rowspan="2"></td><td></td></tr><tr><td>自定义代码埋点</td></tr><tr><td rowspan="2">上报数据</td><td>自动上报数据 手动上报数据</td><td rowspan="2">SDK在满足一定条件后自动发送事件数据</td></tr><tr><td></td><td>SDK支持手动上报事件数据</td></tr><tr><td rowspan="2">调试功能</td><td>调试模式</td><td rowspan="2">开启／关闭调试模式 显示／关闭调试日志</td></tr><tr><td>调试日志</td></tr></table></body></html>

Flutter SDK 目前功能清单要低于原生 SDK 提供的功能，即并未全部包含原生 SDK 的功能。若要使用原生 SDK 提供功能，可在原生端初始化 SDK。具体初始化方式可参考：Android SDK 使用指南 和 iOS SDK 使用指南。  

# 2. 3. SDK 预置事件与预置属性  

参见 App SDK 预置事件与预置属性文档  

<img src="http://103.140.228.128:8000/images/54f2630d84847e694666093db8af554d9bad42514ba084f7cbf821fd704a8cb4.jpg" width="300" alt="产品图片">  

在使用前，请先阅读数据模型、Android SDK 使用指南和 iOS SDK 使用指南  

# 3. 集成神策分析 SDK Flutter 插件  

# 3.1. 引入插件  

在 Flutter 项目的 pubspec.yaml文件中 dependencies 里面添加 universal_statistics__flutter_plugin 依赖。  

dependencies:   
# 添加 flutter plugin   
universal_statistics__flutter_plugin: ^3.0.0  

执行 fluterpubget 命令安装插件。  

# 4. Flutter 插件初始化  

# 4.1. 获取项目数据接收地址  

<img src="http://103.140.228.128:8000/images/fe63f1281e4f55c8f67ffd4a01f669114b9f0591060bdd10b8666e21cc7d551a.jpg" width="300" alt="产品图片">  

每个项目都有单独的数据接收地址请使用管理员账户获取相应项目的数据接收地址  

<img src="http://103.140.228.128:8000/images/c65c1cdfc4d9764939e24891c92015a4e1b6ee6b62d51fd3e27750c6678bd336.jpg" width="300" alt="产品图片">  

# 4.2. 初始化 SDK  

自 Flutter 插件 v2.1.0 开始支持在 Flutter 端进行初始化。示例如下：  

<html><body><table><tr><td>UniversalFlutterPlugin.init(</td></tr><tr><td>serverUrl:</td></tr><tr><td>"数据接收地址",</td></tr><tr><td>autoTrackTypes: <SAAutoTrackType>{</td></tr><tr><td>SAAutoTrackType.APP_START,</td></tr><tr><td>SAAutoTrackType.APP_END</td></tr><tr><td>}，</td></tr><tr><td> networkTypes: <SANetworkType>{</td></tr><tr><td>SANetworkType.TYPE_ALL, }，</td></tr><tr><td>flushlnterval: 10000,</td></tr><tr><td>flushBulkSize: 50,</td></tr><tr><td>enableLog: true,</td></tr><tr><td>javaScriptBridge: true,</td></tr><tr><td>encrypt: true,</td></tr><tr><td>heatMap: true,</td></tr><tr><td> visualized: VisualizedConfig(autoTrack: true, properties: true),</td></tr><tr><td>android: AndroidConfig( maxCacheSize: 48 * 1024 * 1024,</td></tr><tr><td>jellybean: true,</td></tr><tr><td>subProcessFlush: true),</td></tr><tr><td>ios: lOsConfig(maxCacheSize: 10000),</td></tr><tr><td>globalProperties: {aaa': 'aaa-value', 'bbb': 'bbb-value'});</td></tr><tr><td></td></tr></table></body></html>  

注意：通常原生端和 Flutter 端只要初始化一次即可。若选择在 Flutter 端初始化，就不需要再在原生端初始化了。  

# 4.2.1. init() 方法参数说明  

<html><body><table><tr><td>参数名</td><td>参数类型</td><td>参数说明</td><td>备注</td></tr><tr><td>serverUrl</td><td>String?</td><td>数据接收地址</td><td></td></tr><tr><td>enableLog</td><td>bool</td><td>是否显示日志</td><td></td></tr><tr><td>autoTrackTy pes</td><td>Set<SAAutoTrackT ype>?</td><td>全埋点采集类型</td><td>SAAutoTrackType.NONE SAAutoTrackType.START ）SAAutoTrackType.END</td></tr><tr><td>flushlnterval</td><td>int</td><td>设置两次事件上报的最小间隔</td><td>默认15秒，最小5秒，单位毫秒</td></tr><tr><td>flushBulksize</td><td>int</td><td>设置本地缓存触发flush 的最大条目数</td><td>默认100，最小50</td></tr><tr><td>networkTyp es</td><td>Set<SANetworkTyp e>?</td><td>设置上报网络情况</td><td>TYPE_NONE, TYPE_2G, TYPE_3G, TYPE_4G, TYPE_WIFI, TYPE_5G, TYPE_ALL</td></tr><tr><td>encrypt</td><td>bool</td><td>是否开启加密</td><td>仅支持RSA+ AES</td></tr><tr><td>javaScriptBri dge</td><td>bool</td><td>是否支持H5打通</td><td>默认false</td></tr><tr><td>android</td><td>AndroidConfig?</td><td>Android 端特有配置 ·subProcessFlush:是否支持子进程上报数据 ·jellybean:打通是否支持APIlevel16及以下的版本</td><td>android:{ subProcessFlush:true, jellybean:true, maxCacheSize:48 * 1024*1024</td></tr><tr><td>ios</td><td>IOSConfig?</td><td>32* 1024*1024 iOS 端特有配置 maxCacheSize:最大缓存数，单位条。默认值：10000</td><td>ios:{ maxCacheSize:10000</td></tr><tr><td>globalPrope rties</td><td>Map?</td><td>配置全局公共属性</td><td>} 其优先级低于静态公共属性</td></tr></table></body></html>  

<img src="http://103.140.228.128:8000/images/fb0217c400a13d3e27edfd265879929858fca0263b4852ac1f26db08ecc78c98.jpg" width="300" alt="产品图片">  

1.  若 App 有合规需求，可参考 合规说明；  
2.  以上是在 Flutter 代码中进行初始化。老版本的插件不支持这种初始化方式，若需要在原生端初始化，请参考 Android SDK 使用指南和 iOS SDK 使用指南。  

# 5. 配置 Scheme  

# 5.1. 获取项目 Scheme  

<img src="http://103.140.228.128:8000/images/d16b1f34e7c0082ad05da7275c8ee69aa04587fc9c0b942e4de41c56c744df22.jpg" width="300" alt="产品图片">  

项目的 Scheme 需要管理员账户进行获取App 工程中可以同时配置多个项目的 Scheme  

<img src="http://103.140.228.128:8000/images/ac6c3471e0784555546ce56740543bf27fb3c85be9e8d44048e58cdfec470de2.jpg" width="300" alt="产品图片">  

# 5.2. App 中添加 Scheme  

在使用神策系统中的 Debug 实时查看、可视化全埋点等需要扫码的功能时，用于拉起页面。针对 Android 和 iOS 平台，配置方式不一样：  

Android 平台配置 Scheme（此处需要配置链接）iOS 平台配置 Scheme（此处需要配置链接）  

# 6. SDK 基本配置  

# 6.1. 用户关联  

用户关联是为了对用户进行唯一标识，提高用户行为分析的准确性。目前神策提供了简易用户关联和全域用户关联分为用于支撑不同的业务场景。  

简易用户关联（IDM 2.0）全域用户关联（IDM 3.0）  

# 6.2. 设置事件公共属性  

对于所有事件都需要添加的属性，初始化 SDK 后，可以通过 registerSuperProperties() 将属性注册为公共属性。详细使用文档参见基础 API 功能介绍。  

# 6.3. 记录激活事件  

可以调用 trackAppInstall() 方法记录激活事件，多次调用此方法只会在第一次调用时触发激活事件。详细使用文档参见渠道追踪与广告。  

# 6.4. 代码埋点追踪事件  

SDK 初始化后，可以通过 track() 方法追踪用户行为事件，并为事件添加自定义属性。详细使用文档参见基础 API 功能介绍。  

# 7. 调试查看事件信息  

可以在 init() 方法初始化时 enableLog 设置参数为 true。或者调用  

import 'package:universal_statistics_flutter_plugin/universal_statistics_flutter_plugin.dart';   
UniversalFlutterPlugin.enableLog(true/false) //方法来开启或关闭日志。  

# 在 Logcat（Android）或 Xcode（iOS） 中筛选 SA. 关键词：  

埋点事件触发成功时，SDK 会输出 track event 开头的事件数据  
埋点事件触发失败时，SDK 会输出相应的错误原因事件数据上报成功时，SDK 会输出 valid message 字段开头的事件数据  
事件数据上报失败时，SDK 会输出 invalid message 字段开头的事件数据并输出错误原因  