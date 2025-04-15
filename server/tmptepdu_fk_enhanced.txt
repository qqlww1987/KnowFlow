# 【技术方案】大疆 Flutter SDK 技术方案  

1. 需求1.1. 背景和现状1.2. 需求描述  
2. 方案2.1. 方案概述2.2.  源码注释翻译成英文2.3. 全局替换关键词2.4. Android/iOS 埋点 SDK 替换2.4.1.  Android2.4.2. iOS2.5. 修改 lib 桥文件2.5.1.  Android2.5.2.  iOS2.5.2.1. example2.5.2.2.  lib2.6.  发布到 pub dev  
3. 评审记录  

# 1. 需求  

# 1.1. 背景和现状  

【技术方案】大疆定制化 SDK 海外版本  

# 1.2. 需求描述  

Flutter 代码埋点插件Flutter SDK Code 英文sensorsdata 关键词可替换  

# 2. 方案  

# 2.1. 方案概述  

代码中涉及到的注释英文化  
Flutter lib 库关键字替换：【技术方案】大疆定制化 SDK 海外版本  
Flutter 依赖的埋点 SDK 以及桥文件关键词替换  

# 2.2.  源码注释翻译成英文  

将源码注释翻译成英文并将代码上传至 abroad 分支  

# 2.3. 全局替换关键词  

在上述代码基础上执行 main.py 文件，此时会将源码目录下相应关键词一键替换。  

# 2.4. Android/iOS 埋点 SDK 替换  

# 2.4.1.  Android  

需要完成埋点 SDK 的替换  

1.  将 UniversalStatisticsSDK-6.7.7.0.a r放在 android/libs/目录下  
2.  在 build.gradle 文件追加如下配置：  

rootProject.allprojects { repositories { google() mavenCentral() flatDir { dirs project(':universal_statistics_flutter_plugin').file('libs') }  

# 2.4.2. iOS  

在 ios/Classes 目录下放置 iOS SDK 源码  

# 2.5. 修改 lib 桥文件  

# 2.5.1.  Android  

由于 Flutter 插件桥接了 Android 标品 SDK ，目前对 UniversalFlutterPlugin、FlutterVisual 两个文件未做脚本替换，需要手动修改。  

UniversalFlutterPlugin  

修改 class 名称  
package 名称  
MethodChannel 桥文件修改 universal_statistics_flutter_plugin  

FlutterVisual  

package 名称  

以上做修改后，则代码埋点生效。  

# 2.5.2.  iOS  

# 2.5.2.1. example  

脚本误操作了 example/iOS 目录，具体影响的几个文件：  

example/ios/Runner.xcodeproj/project.pbxproj example/ios/Runner/AppDelegate.m  

# 2.5.2.2.  lib  

# 修改 ios/Classes/UniversalFlutterGlobalPropertyPlugin.m 文件  

<img src="http://103.140.228.128:8000/images/950c6ab3f942978945cc09087c53318c5455886f1b0166644bc53374399b897f.jpg" width="300" alt="产品图片">  

# 2.6.  发布到 pub dev  

打包源码，并发布到 pub dev 市场  

# 3. 评审记录  

<html><body><table><tr><td>时间</td><td>参与人员</td><td>内容与结果</td></tr><tr><td>2023-12-12</td><td>韦章翔 邓士伟 陈玉国</td><td>通过</td></tr></table></body></html>  