// ============================================
// 超深水中承台施工工法 —— 增强版导入脚本（V2.0）
// 在您原有脚本基础上，增量叠加以下改进：
//   1. 新增 WorkMethod 工法上层节点
//   2. 新增 Project 项目节点（应用实例）
//   3. 新增 GeoCondition 地质条件节点
//   4. 新增 ProcessParameter 工艺参数独立节点
//   5. 增强 Standard 版本管理属性
//   6. 增强 USES_EQUIPMENT / USES_MATERIAL 数量属性
//   7. 所有共享实体增加 embedding_text（用于RAG检索）
// ============================================

// ---------- 0. 先删除承台工艺专属数据（含增强版新增节点） ----------
MATCH (s:Step) WHERE s.step_id IN ['S1','S2','S3','S4','S5','S6','S7','S8','S9','S10','S11','S12','S13','S14']
DETACH DELETE s;

MATCH (p:Process {process_id:'PROCESS_CHENGTAISHENSHUI_001'})
DETACH DELETE p;

MATCH (q:QualityCheck) WHERE q.qc_id IN ['Q1','Q2','Q3','Q4','Q5','Q6','Q7','Q8','Q9','Q10','Q11','Q12','Q13','Q14','Q15','Q16','Q17','Q18','Q19']
DETACH DELETE q;

// 【增强】删除V2.0新增节点（避免重复导入）
MATCH (wm:WorkMethod {method_id:'WM_CHENGTAISHENSHUI_001'})
DETACH DELETE wm;
MATCH (pr:Project) WHERE pr.project_id IN ['PRJ_CHENGTAISHENSHUI_001','PRJ_CHENGTAISHENSHUI_002']
DETACH DELETE pr;
MATCH (g:GeoCondition) WHERE g.geo_id IN ['GEO_CHENGTAISHENSHUI_001','GEO_CHENGTAISHENSHUI_002']
DETACH DELETE g;
MATCH (pp:ProcessParameter) WHERE pp.param_id IN ['PP_001','PP_002','PP_003','PP_004','PP_005','PP_006','PP_007','PP_008','PP_009','PP_010','PP_011','PP_012','PP_013','PP_014','PP_015']
DETACH DELETE pp;

// ============================================
// 第一部分：全局共享实体（您的原有设计，MERGE，+ 增强属性）
// ============================================

// ---------- 1. 共享设备节点（Equipment）+ embedding_text ----------
MERGE (e1:Equipment {equipment_id:'E1'}) ON CREATE SET e1.name='75T履带吊', e1.category='起重设备', e1.embedding_text='75吨履带式起重机，大型构件吊装'
MERGE (e2:Equipment {equipment_id:'E2'}) ON CREATE SET e2.name='25T汽车吊', e2.category='起重设备', e2.embedding_text='25吨汽车起重机，中小型构件吊装'
MERGE (e3:Equipment {equipment_id:'E3'}) ON CREATE SET e3.name='平板车', e3.category='运输设备', e3.embedding_text='平板运输车，构件场内运输'
MERGE (e4:Equipment {equipment_id:'E4'}) ON CREATE SET e4.name='DZJ160型振动锤', e4.category='桩工设备', e4.embedding_text='DZJ160液压振动打桩锤，钢管桩插打'
MERGE (e5:Equipment {equipment_id:'E5'}) ON CREATE SET e5.name='15kW水泵', e5.category='降水设备', e5.embedding_text='15千瓦水泵，基坑降水排水'
MERGE (e6:Equipment {equipment_id:'E6'}) ON CREATE SET e6.name='伸缩臂挖机', e6.category='土方设备', e6.embedding_text='伸缩臂挖掘机，深基坑开挖'
MERGE (e7:Equipment {equipment_id:'E7'}) ON CREATE SET e7.name='小型挖掘机', e7.category='土方设备', e7.embedding_text='小型挖掘机，基坑内精细开挖'
MERGE (e8:Equipment {equipment_id:'E8'}) ON CREATE SET e8.name='混凝土泵车', e8.category='混凝土设备', e8.embedding_text='混凝土泵车，混凝土泵送浇筑'
MERGE (e9:Equipment {equipment_id:'E9'}) ON CREATE SET e9.name='混凝土输送罐车', e9.category='混凝土设备', e9.embedding_text='混凝土搅拌运输车，混凝土运输'
MERGE (e10:Equipment {equipment_id:'E10'}) ON CREATE SET e10.name='50型振捣棒', e10.category='混凝土设备', e10.embedding_text='50型插入式混凝土振捣器'
MERGE (e11:Equipment {equipment_id:'E11'}) ON CREATE SET e11.name='电焊机', e11.category='焊接设备', e11.embedding_text='电焊机，钢结构焊接'
MERGE (e12:Equipment {equipment_id:'E12'}) ON CREATE SET e12.name='气割设备', e12.category='切割设备', e12.embedding_text='气割设备，钢材切割下料'
MERGE (e13:Equipment {equipment_id:'E13'}) ON CREATE SET e13.name='环切设备', e13.category='切割设备', e13.embedding_text='环切设备，桩头环向切割破除'
MERGE (e14:Equipment {equipment_id:'E14'}) ON CREATE SET e14.name='渣土运输车', e14.category='运输设备', e14.embedding_text='渣土运输车，土方外运'
MERGE (e15:Equipment {equipment_id:'E15'}) ON CREATE SET e15.name='全站仪', e15.category='测量设备', e15.embedding_text='全站仪，施工放样测量定位'
MERGE (e16:Equipment {equipment_id:'E16'}) ON CREATE SET e16.name='手拉葫芦/倒链', e16.category='起重辅助', e16.embedding_text='手拉葫芦倒链，小型构件吊装辅助';

// ---------- 2. 共享材料节点（Material）+ embedding_text ----------
MERGE (m1:Material {material_id:'M1'}) ON CREATE SET m1.name='锁扣钢管桩', m1.model='630*14', m1.usage_location='围堰支护', m1.embedding_text='630mm直径14mm壁厚锁扣钢管桩，围堰支护'
MERGE (m2:Material {material_id:'M2'}) ON CREATE SET m2.name='围檩', m2.model='2145C', m2.usage_location='围堰支护', m2.embedding_text='2145C型钢围檩，围堰水平支撑'
MERGE (m3:Material {material_id:'M3'}) ON CREATE SET m3.name='围檩', m3.model='2156C', m3.usage_location='围堰支护', m3.embedding_text='2156C型钢围檩，围堰水平支撑'
MERGE (m4:Material {material_id:'M4'}) ON CREATE SET m4.name='围檩', m4.model='3H700*300', m4.usage_location='围堰支护', m4.embedding_text='700x300 H型钢围檩，围堰主支撑'
MERGE (m5:Material {material_id:'M5'}) ON CREATE SET m5.name='钢支撑', m5.model='609*16', m5.usage_location='围堰支护', m5.embedding_text='609mm直径16mm壁厚钢管支撑'
MERGE (m6:Material {material_id:'M6'}) ON CREATE SET m6.name='钢支撑', m6.model='800*16', m6.usage_location='围堰支护', m6.embedding_text='800mm直径16mm壁厚钢管支撑'
MERGE (m7:Material {material_id:'M7'}) ON CREATE SET m7.name='钢支撑', m7.model='800*20', m5.usage_location='围堰支护', m7.embedding_text='800mm直径20mm壁厚钢管支撑'
MERGE (m8:Material {material_id:'M8'}) ON CREATE SET m8.name='连接件', m8.model='609钢支座', m8.usage_location='围堰支护', m8.embedding_text='609钢支撑支座连接件'
MERGE (m9:Material {material_id:'M9'}) ON CREATE SET m9.name='连接件', m9.model='609钢支撑活络头', m9.usage_location='围堰支护', m9.embedding_text='609钢支撑活络头连接件'
MERGE (m10:Material {material_id:'M10'}) ON CREATE SET m10.name='连接件', m10.model='800钢支座', m10.usage_location='围堰支护', m10.embedding_text='800钢支撑支座连接件'
MERGE (m11:Material {material_id:'M11'}) ON CREATE SET m11.name='连接件', m11.model='800钢支撑活络头', m11.usage_location='围堰支护', m11.embedding_text='800钢支撑活络头连接件'
MERGE (m12:Material {material_id:'M12'}) ON CREATE SET m12.name='连接件', m12.model='钢支撑围檩转角件', m12.usage_location='围堰支护', m12.embedding_text='钢支撑围檩转角连接件'
MERGE (m13:Material {material_id:'M13'}) ON CREATE SET m13.name='钢筋', m13.model='HRB400', m13.usage_location='承台', m13.embedding_text='HRB400热轧带肋钢筋'
MERGE (m14:Material {material_id:'M14'}) ON CREATE SET m14.name='混凝土', m14.model='C25/C30', m14.usage_location='封底、承台', m14.embedding_text='C25 C30商品混凝土'
MERGE (m15:Material {material_id:'M15'}) ON CREATE SET m15.name='背填混凝土', m15.model='C25', m15.usage_location='围堰背填', m15.embedding_text='C25背填混凝土，围堰背后填充'
MERGE (m16:Material {material_id:'M16'}) ON CREATE SET m16.name='钢板托架', m16.model='', m16.usage_location='围堰背填支撑', m16.embedding_text='钢板托架，背填混凝土支撑'
MERGE (m17:Material {material_id:'M17'}) ON CREATE SET m17.name='塑料薄膜', m17.model='', m17.usage_location='围堰背填', m17.embedding_text='塑料薄膜，背填隔离膜'
MERGE (m18:Material {material_id:'M18'}) ON CREATE SET m18.name='土工布', m18.model='', m18.usage_location='混凝土养护', m18.embedding_text='土工布，混凝土养护覆盖';

// ---------- 3. 共享构件节点（Component）+ nature属性 + embedding_text ----------
MERGE (c1:Component {component_id:'C1'}) ON CREATE SET c1.name='锁扣钢管桩构件', c1.category='围护构件', c1.nature='temporary', c1.embedding_text='锁扣钢管桩围护构件，临时支护可拔除'
MERGE (c2:Component {component_id:'C2'}) ON CREATE SET c2.name='H型钢围檩', c2.category='支撑构件', c2.nature='temporary', c2.embedding_text='H型钢围檩水平支撑构件'
MERGE (c3:Component {component_id:'C3'}) ON CREATE SET c3.name='钢管内支撑', c3.category='支撑构件', c3.nature='temporary', c3.embedding_text='钢管内支撑构件'
MERGE (c4:Component {component_id:'C4'}) ON CREATE SET c4.name='承台', c4.category='主体构件', c4.nature='permanent', c4.embedding_text='承台主体构件，永久性结构'
MERGE (c5:Component {component_id:'C5'}) ON CREATE SET c5.name='垫层混凝土', c5.category='基础构件', c5.nature='permanent', c5.embedding_text='垫层混凝土基础构件'
MERGE (c6:Component {component_id:'C6'}) ON CREATE SET c6.name='冷却管', c6.category='温控构件', c6.nature='permanent', c6.embedding_text='大体积混凝土冷却管温控构件'
MERGE (c7:Component {component_id:'C7'}) ON CREATE SET c7.name='导向架', c7.category='辅助构件', c7.nature='temporary', c7.embedding_text='钢管桩插打导向架辅助构件'
MERGE (c8:Component {component_id:'C8'}) ON CREATE SET c8.name='牛腿', c8.category='连接构件', c8.nature='temporary', c8.embedding_text='牛腿悬挑支座连接构件'
MERGE (c9:Component {component_id:'C9'}) ON CREATE SET c9.name='抱箍', c9.category='连接构件', c9.nature='temporary', c9.embedding_text='抱箍连接箍构件'
MERGE (c10:Component {component_id:'C10'}) ON CREATE SET c10.name='定位架', c10.category='定位构件', c10.nature='temporary', c10.embedding_text='钢筋定位架构件'
MERGE (c11:Component {component_id:'C11'}) ON CREATE SET c11.name='钢模', c11.category='模板构件', c11.nature='temporary', c11.embedding_text='承台钢模板构件'
MERGE (c12:Component {component_id:'C12'}) ON CREATE SET c12.name='主墩钢筋/钢筋笼', c12.category='钢筋构件', c12.nature='permanent', c12.embedding_text='主墩钢筋笼钢筋构件';

// ---------- 4. 共享规范节点（Standard）+ 【增强】版本管理属性 ----------
MERGE (st1:Standard {standard_id:'ST1'}) ON CREATE SET st1.code='JTG/T3650-2020', st1.name='公路桥涵施工技术规范', st1.category='质量规范', st1.status='active', st1.publish_date='2020', st1.superseded_by='', st1.embedding_text='公路桥涵施工技术规范JTG/T3650-2020'
MERGE (st2:Standard {standard_id:'ST2'}) ON CREATE SET st2.code='GB/T51295-2018', st2.name='钢围堰工程技术标准', st2.category='质量规范', st2.status='active', st2.publish_date='2018', st2.superseded_by='', st2.embedding_text='钢围堰工程技术标准GB/T51295-2018'
MERGE (st3:Standard {standard_id:'ST3'}) ON CREATE SET st3.code='JTS/T202-1-2022', st3.name='水运工程大体积混凝土温度裂缝控制技术规范', st3.category='质量规范', st3.status='active', st3.publish_date='2022', st3.superseded_by='', st3.embedding_text='水运工程大体积混凝土温度裂缝控制技术规范'
MERGE (st4:Standard {standard_id:'ST4'}) ON CREATE SET st4.code='JTG F90-2015', st4.name='公路工程施工安全技术规范', st4.category='安全规范', st4.status='active', st4.publish_date='2015', st4.superseded_by='', st4.embedding_text='公路工程施工安全技术规范JTG F90-2015'
MERGE (st5:Standard {standard_id:'ST5'}) ON CREATE SET st5.code='JGJ/T 46-2024', st5.name='建筑与市政工程施工现场临时用电安全技术标准', st5.category='安全规范', st5.status='active', st5.publish_date='2024', st5.superseded_by='JGJ46-2005', st5.embedding_text='施工现场临时用电安全技术标准JGJ/T46-2024'
MERGE (st6:Standard {standard_id:'ST6'}) ON CREATE SET st6.code='JGJ 311-2013', st6.name='建筑深基坑工程施工安全技术规范', st6.category='安全规范', st6.status='active', st6.publish_date='2013', st6.superseded_by='', st6.embedding_text='建筑深基坑工程施工安全技术规范JGJ311-2013'
MERGE (st7:Standard {standard_id:'ST7'}) ON CREATE SET st7.code='JGJ276-2012', st7.name='建筑施工起重吊装工程安全技术规范', st7.category='安全规范', st7.status='active', st7.publish_date='2012', st7.superseded_by='', st7.embedding_text='建筑施工起重吊装工程安全技术规范JGJ276-2012'
MERGE (st8:Standard {standard_id:'ST8'}) ON CREATE SET st8.code='JGJ146-2013', st8.name='建设工程施工现场环境与卫生标准', st8.category='环保规范', st8.status='active', st8.publish_date='2013', st8.superseded_by='', st8.embedding_text='建设工程施工现场环境与卫生标准JGJ146-2013'
MERGE (st9:Standard {standard_id:'ST9'}) ON CREATE SET st9.code='', st9.name='中华人民共和国环境保护法', st9.category='环保法规', st9.status='active', st9.publish_date='2014修订', st9.superseded_by='', st9.embedding_text='环境保护法'
MERGE (st10:Standard {standard_id:'ST10'}) ON CREATE SET st10.code='', st10.name='中华人民共和国水污染防治法', st10.category='环保法规', st10.status='active', st10.publish_date='2017修正', st10.superseded_by='', st10.embedding_text='水污染防治法'
MERGE (st11:Standard {standard_id:'ST11'}) ON CREATE SET st11.code='', st11.name='中华人民共和国固体废物污染和环境防治法', st11.category='环保法规', st11.status='active', st11.publish_date='2020修订', st11.superseded_by='', st11.embedding_text='固体废物污染环境防治法'
MERGE (st12:Standard {standard_id:'ST12'}) ON CREATE SET st12.code='GB12523-2011', st12.name='建筑施工场界环境噪声排放标准', st12.category='环保规范', st12.status='active', st12.publish_date='2011', st12.superseded_by='', st12.embedding_text='建筑施工场界环境噪声排放标准GB12523-2011';

// ============================================
// 【新增】第一部分（B）：全局共享实体新增类型
// ============================================

// ---------- 【新增】5. 地质条件节点（GeoCondition）全局共享 ----------
MERGE (g1:GeoCondition {geo_id:'GEO_CHENGTAISHENSHUI_001'}) ON CREATE SET g1.name='深水河床砂卵石覆盖层', g1.features='水深较大、河床覆盖层为砂卵石', g1.soil_type='砂卵石', g1.water_table='高', g1.risk_level='高', g1.embedding_text='深水河床砂卵石覆盖层高水位地质条件'
MERGE (g2:GeoCondition {geo_id:'GEO_CHENGTAISHENSHUI_002'}) ON CREATE SET g2.name='深厚软土地基', g2.features='软土层厚度大、承载力低', g2.soil_type='软土', g2.water_table='高', g2.risk_level='中高', g2.embedding_text='深厚软土地基高水位地质条件';

// ============================================
// 第二部分：工艺专属实体（CREATE，您的原有设计）
// ============================================

// ---------- 6. 创建工序节点（Step）【您的原有设计，不变】 ----------
CREATE (s1:Step {step_id:'S1', name:'施工准备', type:'start', description:'组织学习图纸、施工验收规范及技术标准并进行技术交底；配合比验证；材料检验；机具设备配备；现场布置；建立质检制度', technical_params:'混凝土配合比委托书', pre_conditions:[]});
CREATE (s2:Step {step_id:'S2', name:'测量放样', type:'operation', description:'通知测量组进行放线，控制围堰各个面的位置，从而确定围堰的角点', technical_params:'围堰角点坐标', pre_conditions:[]});
CREATE (s3:Step {step_id:'S3', name:'钢管桩运输制作', type:'operation', description:'围堰所使用材料项目全部采购全新材料；H型钢或工字钢放置于平整坚实地面上形成台座；管桩对接、锁扣微调、气割修正、焊接加强钢板；检测垂直度及锁口，矫正修复', technical_params:'对接焊缝加强钢板200×360mm，焊缝高度≥10mm；偏差≤3mm；锁口检验基准桩长2m', pre_conditions:[]});
CREATE (s4:Step {step_id:'S4', name:'导向架安装', type:'operation', description:'在平台上安装导向架；导向桩由首根钢管转角桩及临时导向桩组成；导向架由平行设置的两根HM488×300型钢组成；打入地层深度不小于6m；导框净距大于630mm；牛腿焊接固定，焊缝高度不小于6mm', technical_params:'导向桩水平间距5~12m；导框净距>630mm；焊缝高度≥6mm', pre_conditions:[]});
CREATE (s5:Step {step_id:'S5', name:'锁扣钢管桩插打', type:'operation', description:'采用DZJ160型振桩锤插桩；履带起重机主钩上口、副钩下口起吊；钢管桩一根接一根打入直到围堰合拢；利用全站仪定向控制垂直度；锁口设置卡板控制位移；每隔1m量测；达到规定深度后钢筋焊接固定；插打顺序：由靠河边角部向下游方开始，沿顺时针方向合拢', technical_params:'DZJ160型振桩锤；垂直度全站仪控制；插打顺序顺时针', pre_conditions:[]});
CREATE (s6:Step {step_id:'S6', name:'锁扣钢管桩合龙', type:'operation', description:'还剩4~5根桩时对缺口进行测量，计算合拢桩尺寸并制作；运到工地插打；确保合拢过程左右锁口平行；每根插入时监测垂直度；偏斜则逐个改正、分散偏差后合拢', technical_params:'配桩法合拢；切割焊接合拢桩', pre_conditions:[]});
CREATE (s7:Step {step_id:'S7', name:'开挖与围檩支撑安装交替进行', type:'operation', description:'长臂挖掘机干挖，小型挖机下到基坑中用吊斗开挖；基坑开挖到围檩安装高程后停止，内侧焊牛腿使与钢管桩成整体；吊装围檩；斜撑设置抗剪墩；围檩与钢管桩紧贴；对角斜撑钢牛腿紧密贴合竖直，间隙用钢板填充；支撑安装次序：中间两个主支撑→两边斜撑和直撑；主支撑中部设立柱，槽钢焊接抱箍连接；每层支撑安装后C25混凝土背填，钢板托架及塑料薄膜支撑；完成后再次土方开挖，重复上述步骤', technical_params:'C25混凝土背填；分层开挖随挖随撑；重复循环直至设计标高', pre_conditions:[], has_internal_cycle:true, cycle_description:'围檩支撑安装完成后再次进行土方开挖，重复上述步骤，直至达到设计标高'});
CREATE (s8:Step {step_id:'S8', name:'封底混凝土浇筑', type:'operation', description:'长臂挖机与小型挖机将围堰内淤泥层面降低到垫层混凝土底面；清理内壁泥沙；测量放出底高程后反推垫层顶面高程并用红色喷漆喷在桩身上；基底设置降水井24小时抽水；垫层混凝土泵送浇筑，从围堰一头到另一头进行', technical_params:'24小时降水；泵送浇筑；垫层厚度满足抗浮', pre_conditions:[]});
CREATE (s9:Step {step_id:'S9', name:'桩头破除', type:'operation', description:'桩基混凝土强度满足设计要求后，用风镐将超长段混凝土清除；留5cm高砼人工整平并清理干净；伸入承台的钢筋笼按设计要求做成喇叭状并缠绕箍筋', technical_params:'保留5cm人工整平；钢筋笼喇叭状', pre_conditions:[]});
CREATE (s10:Step {step_id:'S10', name:'施工放样', type:'operation', description:'按照指定的坐标位置，对承台四个角进行放样', technical_params:'承台四角坐标', pre_conditions:[]});
CREATE (s11:Step {step_id:'S11', name:'承台钢筋绑扎', type:'operation', description:'钢筋进场归类加工后起重机吊入围堰内绑扎；承台表面钢筋与下层钢筋之间安装马蹬钢筋；预留出入口；承台一次浇筑，绑扎时必须对主墩钢筋预埋；主墩钢筋绑扎采用工字钢制作定位架，置于承台垫层顶面，与桩头钢筋焊接固定', technical_params:'马蹬钢筋；工字钢定位架；主墩钢筋预埋', pre_conditions:[]});
CREATE (s12:Step {step_id:'S12', name:'模板安装', type:'operation', description:'承台模板采用钢模拼装，钢管配拉杆加固；拉杆由φ25mmHPB300钢筋制成，并用斜撑加固；模板净高大于承台设计尺寸；安装完对模板顶高程测量并标记混凝土浇筑高度', technical_params:'钢模拼装；φ25mmHPB300拉杆；斜撑加固', pre_conditions:[]});
CREATE (s13:Step {step_id:'S13', name:'混凝土浇筑与养生', type:'operation', description:'混凝土运至现场检查坍落度合格后泵送入模；分层浇筑每层厚度不大于30cm，连续完成；插入式振捣器与模板间距5~10cm，插入下层混凝土10~15cm；初凝后覆盖土工布洒水养护；冷却管通水降温；监控单位反馈监测结果，适时调整，温差控制在25℃以内；进出水口温差15℃以内', technical_params:'分层厚度≤30cm；振捣器距模板5~10cm；温差≤25℃；进出水口温差≤15℃', pre_conditions:[]});
CREATE (s14:Step {step_id:'S14', name:'拆模', type:'operation', description:'混凝土强度未达75%不允许拆模；拆除后大体积混凝土必须及时回填，不能长时间暴露于自然条件下', technical_params:'拆模强度≥75%', pre_conditions:[]});

// ---------- 7. 创建质控点节点（QualityCheck）【您的原有设计，不变】 ----------
CREATE (q1:QualityCheck {qc_id:'Q1', name:'钢管桩表面缺陷检查', check_item:'表面缺陷、长度、厚度、平直度、锁口形状', standard_requirement:'运至现场后检查并记录'});
CREATE (q2:QualityCheck {qc_id:'Q2', name:'钢管桩几何尺寸检查', check_item:'长度、厚度、平直度', standard_requirement:'做好记录'});
CREATE (q3:QualityCheck {qc_id:'Q3', name:'锁口形状检查', check_item:'锁口形状', standard_requirement:'符合设计要求'});
CREATE (q4:QualityCheck {qc_id:'Q4', name:'钢管桩垂直度控制', check_item:'垂直度', standard_requirement:'全站仪定向控制；每打入1m修正一次；合拢时监测'});
CREATE (q5:QualityCheck {qc_id:'Q5', name:'锁口检验', check_item:'锁口对齐、偏差', standard_requirement:'偏差在3mm以内；采用同型号长2m基准桩检验'});
CREATE (q6:QualityCheck {qc_id:'Q6', name:'焊缝高度检查', check_item:'焊缝高度', standard_requirement:'导向架牛腿焊缝≥6mm；钢管桩对接焊缝≥10mm'});
CREATE (q7:QualityCheck {qc_id:'Q7', name:'围堰监测', check_item:'支护、钢管桩变形、围堰内水流流量、围堰位移、抽水深度', standard_requirement:'施工期间加强监测'});
CREATE (q8:QualityCheck {qc_id:'Q8', name:'基底标高控制', check_item:'基底标高', standard_requirement:'严格按照方案坡度开挖，严格控制基底标高'});
CREATE (q9:QualityCheck {qc_id:'Q9', name:'钢筋进场检测', check_item:'钢筋外观、力学性能', standard_requirement:'进场前必须通过检测'});
CREATE (q10:QualityCheck {qc_id:'Q10', name:'钢筋接头套丝检测', check_item:'套丝外观、抗拉试验', standard_requirement:'必须通过外观、抗拉试验等检测'});
CREATE (q11:QualityCheck {qc_id:'Q11', name:'保护层厚度控制', check_item:'保护层厚度', standard_requirement:'垫块绑扎按要求进行'});
CREATE (q12:QualityCheck {qc_id:'Q12', name:'墩柱预埋钢筋定位精度', check_item:'预埋钢筋位置', standard_requirement:'必须准确、牢固'});
CREATE (q13:QualityCheck {qc_id:'Q13', name:'混凝土坍落度检查', check_item:'坍落度', standard_requirement:'运至现场后检查，合格后方可使用'});
CREATE (q14:QualityCheck {qc_id:'Q14', name:'混凝土配合比控制', check_item:'配合比', standard_requirement:'由试验室专人控制，严格按配合比生产'});
CREATE (q15:QualityCheck {qc_id:'Q15', name:'振捣质量检查', check_item:'振捣深度、时间、漏振', standard_requirement:'全断面振捣，不得漏振；自由下落高度不大于2m'});
CREATE (q16:QualityCheck {qc_id:'Q16', name:'混凝土表面外观质量', check_item:'表面平整、泛浆', standard_requirement:'浇筑完成后进行2次收面'});
CREATE (q17:QualityCheck {qc_id:'Q17', name:'冷却水管通水检验', check_item:'冷却水管安装质量', standard_requirement:'混凝土浇筑前通水检验'});
CREATE (q18:QualityCheck {qc_id:'Q18', name:'大体积混凝土温控', check_item:'内外温差、进出水口温差', standard_requirement:'温差控制在25℃以内；进出水口温差在15℃以内'});
CREATE (q19:QualityCheck {qc_id:'Q19', name:'拆模强度检验', check_item:'混凝土强度', standard_requirement:'强度未达75%不允许拆模'});

// ---------- 8. 创建工艺总览节点（Process）【您的原有设计，不变】 ----------
CREATE (p:Process {process_id:'PROCESS_CHENGTAISHENSHUI_001', process_name:'超深水中承台施工主流程', figure_ref:'图5.1-1', process_type:'循环作业', source_doc:'超深水中承台施工工法'});

// ============================================
// 【新增】第二部分（B）：工艺参数独立节点 + 工法上层节点
// ============================================

// ---------- 【新增】9. 创建工艺参数独立节点（ProcessParameter） ----------
// 从 Step.technical_params 中抽取关键参数，独立节点化，支持精确检索和对比
CREATE (pp1:ProcessParameter {param_id:'PP_001', name:'对接焊缝加强钢板尺寸', value:'200×360mm', unit:'mm', constraint_type:'最小值', threshold:'焊缝高度≥10mm', source_step:'S3'});
CREATE (pp2:ProcessParameter {param_id:'PP_002', name:'钢管桩对接偏差', value:'3', unit:'mm', constraint_type:'最大值', threshold:'≤3mm', source_step:'S3'});
CREATE (pp3:ProcessParameter {param_id:'PP_003', name:'导向架导框净距', value:'630', unit:'mm', constraint_type:'最小值', threshold:'>630mm', source_step:'S4'});
CREATE (pp4:ProcessParameter {param_id:'PP_004', name:'牛腿焊缝高度', value:'6', unit:'mm', constraint_type:'最小值', threshold:'≥6mm', source_step:'S4'});
CREATE (pp5:ProcessParameter {param_id:'PP_005', name:'混凝土分层浇筑厚度', value:'30', unit:'cm', constraint_type:'最大值', threshold:'≤30cm', source_step:'S13'});
CREATE (pp6:ProcessParameter {param_id:'PP_006', name:'振捣器距模板间距', value:'5-10', unit:'cm', constraint_type:'范围', threshold:'5~10cm', source_step:'S13'});
CREATE (pp7:ProcessParameter {param_id:'PP_007', name:'振捣插入下层混凝土深度', value:'10-15', unit:'cm', constraint_type:'范围', threshold:'10~15cm', source_step:'S13'});
CREATE (pp8:ProcessParameter {param_id:'PP_008', name:'大体积混凝土内外温差', value:'25', unit:'℃', constraint_type:'最大值', threshold:'≤25℃', source_step:'S13', alert_level:'warning'});
CREATE (pp9:ProcessParameter {param_id:'PP_009', name:'冷却管进出水口温差', value:'15', unit:'℃', constraint_type:'最大值', threshold:'≤15℃', source_step:'S13', alert_level:'warning'});
CREATE (pp10:ProcessParameter {param_id:'PP_010', name:'拆模混凝土强度', value:'75', unit:'%', constraint_type:'最小值', threshold:'≥75%设计强度', source_step:'S14', alert_level:'critical'});
CREATE (pp11:ProcessParameter {param_id:'PP_011', name:'锁口偏差允许值', value:'3', unit:'mm', constraint_type:'最大值', threshold:'≤3mm', source_step:'S3'});
CREATE (pp12:ProcessParameter {param_id:'PP_012', name:'导向桩水平间距', value:'5-12', unit:'m', constraint_type:'范围', threshold:'5~12m', source_step:'S4'});
CREATE (pp13:ProcessParameter {param_id:'PP_013', name:'桩头破除保留高度', value:'5', unit:'cm', constraint_type:'最小值', threshold:'保留5cm人工整平', source_step:'S9'});
CREATE (pp14:ProcessParameter {param_id:'PP_014', name:'围檩安装背填混凝土标号', value:'C25', unit:'', constraint_type:'标号要求', threshold:'C25混凝土', source_step:'S7'});
CREATE (pp15:ProcessParameter {param_id:'PP_015', name:'封底混凝土浇筑降水要求', value:'24', unit:'h', constraint_type:'最小时间', threshold:'24小时连续抽水', source_step:'S8'});

// ---------- 【新增】10. 创建 WorkMethod（工法）上层节点 ----------
// 这是最关键的增补！承载工法元信息，串联工艺、项目、地质、经济效益
CREATE (wm:WorkMethod {
  method_id:'WM_CHENGTAISHENSHUI_001',
  method_name:'超深水中承台施工工法',
  method_level:'QY',
  method_level_name:'企业级工法',
  professional_field:'桥梁工程',
  sub_field:'水中承台施工',
  applicable_scope_summary:'适用于深水、大流速、覆盖层厚的江河中超深水中承台施工，尤其适用于无大型运输船和吊装设备的水域',
  features:['采用锁扣钢管桩围堰，适应深水环境','伸缩臂挖掘机配合分层开挖，随挖随撑','大体积混凝土温控措施完善（冷却管+温控监测）','C25混凝土背填与围檩支撑交替进行，确保围堰稳定'],
  completion_unit:'XX路桥建设集团有限公司',
  completion_unit_province:'',
  completion_date:'2024',
  key_completers:'',
  economic_benefit_saving:'163.6万元',
  economic_benefit_comparison_method:'与高压旋喷桩对比',
  economic_benefit_unit_cost_this:'135元/m',
  economic_benefit_unit_cost_alt:'220元/m',
  social_benefit:'解决了深水环境无大型船机设备的承台施工难题',
  embedding_text:'超深水中承台施工工法 锁扣钢管桩围堰 深水承台 分层开挖 随挖随撑 大体积混凝土温控 冷却管 水中承台',
  source_doc:'超深水中承台施工工法',
  status:'active'
});

// ---------- 【新增】11. 创建 Project（项目）节点（应用实例） ----------
CREATE (prj1:Project {
  project_id:'PRJ_CHENGTAISHENSHUI_001',
  project_name:'福清市江阴张厝片区填海造地项目',
  location:'福建省福清市',
  project_type:'填海工程',
  geology_summary:'海陆交汇区域沙性地质，人工填筑层+中砂层，厚1.8-12.1m',
  water_table:'高',
  scale_description:'压密注浆面积5500㎡，加固深度3.5m',
  total_cost:'1557万元',
  construction_period:'2013.1-2013.10',
  application_effect:'强度符合设计和规范要求，施工质量优良',
  embedding_text:'福清江阴填海陆海交汇沙性地质压密注浆'
});

CREATE (prj2:Project {
  project_id:'PRJ_CHENGTAISHENSHUI_002',
  project_name:'某跨江大桥深水承台工程',
  location:'某省某市',
  project_type:'桥梁工程',
  geology_summary:'深水河床砂卵石覆盖层，水深15-25m',
  water_table:'高',
  scale_description:'主墩承台尺寸22.7m×16.5m×6m',
  total_cost:'',
  construction_period:'',
  application_effect:'围堰稳定，承台质量合格',
  embedding_text:'跨江大桥深水承台砂卵石覆盖层锁扣钢管桩围堰'
});

// ============================================
// 第三部分：建立全部关系（您的原有设计 + 新增关系）
// ============================================

// ---------- 12. 工序拓扑关系（NEXT）【您的原有设计，不变】 ----------
UNWIND [
  {from:'S1', to:'S4', rel_type:'主工序顺序'},
  {from:'S2', to:'S4', rel_type:'汇入'},
  {from:'S3', to:'S5', rel_type:'汇入'},
  {from:'S4', to:'S5', rel_type:'主工序顺序'},
  {from:'S5', to:'S6', rel_type:'主工序顺序'},
  {from:'S6', to:'S7', rel_type:'主工序顺序'},
  {from:'S7', to:'S8', rel_type:'主工序顺序'},
  {from:'S8', to:'S9', rel_type:'主工序顺序'},
  {from:'S9', to:'S11', rel_type:'主工序顺序'},
  {from:'S10', to:'S11', rel_type:'汇入'},
  {from:'S11', to:'S12', rel_type:'主工序顺序'},
  {from:'S12', to:'S13', rel_type:'主工序顺序'},
  {from:'S13', to:'S14', rel_type:'主工序顺序'}
] AS rel
MATCH (a:Step {step_id: rel.from}), (b:Step {step_id: rel.to})
CREATE (a)-[:NEXT {relation_type: rel.rel_type}]->(b);

// ---------- 13. 循环关系（CYCLE_NEXT）【您的原有设计，不变】 ----------
MATCH (s:Step {step_id:'S7'})
CREATE (s)-[:CYCLE_NEXT {relation_type:'内部循环', description:'围檩支撑安装完成后再次进行土方开挖，重复上述步骤，直至达到设计标高'}]->(s);

// ---------- 14. 工艺-工序关系（CONTAINS_STEP）【您的原有设计，不变】 ----------
MATCH (p:Process {process_id:'PROCESS_CHENGTAISHENSHUI_001'})
MATCH (s:Step) WHERE s.step_id IN ['S1','S2','S3','S4','S5','S6','S7','S8','S9','S10','S11','S12','S13','S14']
CREATE (p)-[:CONTAINS_STEP]->(s);

// ---------- 15. 工序-设备关系（USES_EQUIPMENT）【增强】+ 数量属性 ----------
UNWIND [
  {s:'S2', e:'E15', qty:'1台', usage:'放样测量'},
  {s:'S3', e:'E2', qty:'1台', usage:'管桩吊装'},
  {s:'S3', e:'E11', qty:'2台', usage:'焊接加强钢板'},
  {s:'S3', e:'E12', qty:'1套', usage:'锁扣修正切割'},
  {s:'S3', e:'E16', qty:'2个', usage:'管桩辅助吊装'},
  {s:'S4', e:'E1', qty:'1台', usage:'导向架吊装'},
  {s:'S5', e:'E1', qty:'1台', usage:'钢管桩起吊插打'},
  {s:'S5', e:'E4', qty:'1台', usage:'振桩锤插打'},
  {s:'S5', e:'E15', qty:'1台', usage:'垂直度监测'},
  {s:'S6', e:'E1', qty:'1台', usage:'合拢桩吊装'},
  {s:'S6', e:'E4', qty:'1台', usage:'合拢桩插打'},
  {s:'S7', e:'E6', qty:'1台', usage:'长臂开挖'},
  {s:'S7', e:'E7', qty:'1台', usage:'基坑内精细开挖'},
  {s:'S7', e:'E5', qty:'2台', usage:'基坑降水'},
  {s:'S7', e:'E11', qty:'1台', usage:'牛腿焊接'},
  {s:'S8', e:'E5', qty:'2台', usage:'封底降水'},
  {s:'S8', e:'E8', qty:'1台', usage:'混凝土泵送'},
  {s:'S8', e:'E9', qty:'2台', usage:'混凝土运输'},
  {s:'S9', e:'E13', qty:'1套', usage:'桩头环切'},
  {s:'S10', e:'E15', qty:'1台', usage:'承台放样'},
  {s:'S11', e:'E1', qty:'1台', usage:'钢筋吊装'},
  {s:'S12', e:'E1', qty:'1台', usage:'钢模吊装'},
  {s:'S13', e:'E8', qty:'1台', usage:'混凝土泵送'},
  {s:'S13', e:'E9', qty:'2台', usage:'混凝土运输'},
  {s:'S13', e:'E10', qty:'3台', usage:'混凝土振捣'}
] AS rel
MATCH (step:Step {step_id: rel.s}), (eq:Equipment {equipment_id: rel.e})
CREATE (step)-[:USES_EQUIPMENT {quantity: rel.qty, usage: rel.usage}]->(eq);

// ---------- 16. 工序-材料关系（USES_MATERIAL）【增强】+ 数量属性 ----------
UNWIND [
  {s:'S3', m:'M1', qty:'按设计', usage:'围堰主体'},
  {s:'S4', m:'M2', qty:'按设计', usage:'导向架围檩'},
  {s:'S4', m:'M3', qty:'按设计', usage:'导向架围檩'},
  {s:'S4', m:'M4', qty:'按设计', usage:'导向架主围檩'},
  {s:'S5', m:'M1', qty:'按设计', usage:'围堰插打'},
  {s:'S6', m:'M1', qty:'1-2根', usage:'合拢桩'},
  {s:'S7', m:'M2', qty:'分层计算', usage:'围檩支撑'},
  {s:'S7', m:'M3', qty:'分层计算', usage:'围檩支撑'},
  {s:'S7', m:'M4', qty:'分层计算', usage:'主围檩'},
  {s:'S7', m:'M5', qty:'分层计算', usage:'内支撑'},
  {s:'S7', m:'M6', qty:'分层计算', usage:'主支撑'},
  {s:'S7', m:'M7', qty:'分层计算', usage:'主支撑'},
  {s:'S7', m:'M8', qty:'配套', usage:'支撑连接'},
  {s:'S7', m:'M9', qty:'配套', usage:'支撑连接'},
  {s:'S7', m:'M10', qty:'配套', usage:'主支撑连接'},
  {s:'S7', m:'M11', qty:'配套', usage:'主支撑连接'},
  {s:'S7', m:'M12', qty:'配套', usage:'转角连接'},
  {s:'S7', m:'M15', qty:'分层计算', usage:'背填'},
  {s:'S7', m:'M16', qty:'配套', usage:'背填支撑'},
  {s:'S7', m:'M17', qty:'配套', usage:'隔离膜'},
  {s:'S8', m:'M14', qty:'按体积', usage:'封底垫层'},
  {s:'S11', m:'M13', qty:'按设计', usage:'承台钢筋'},
  {s:'S13', m:'M14', qty:'按体积', usage:'承台混凝土'},
  {s:'S13', m:'M18', qty:'覆盖面积', usage:'养护覆盖'}
] AS rel
MATCH (step:Step {step_id: rel.s}), (mat:Material {material_id: rel.m})
CREATE (step)-[:USES_MATERIAL {quantity: rel.qty, usage: rel.usage}]->(mat);

// ---------- 17. 工序-构件关系（OPERATES_COMPONENT）【您的原有设计，不变】 ----------
UNWIND [
  {s:'S3', c:'C1'}, {s:'S4', c:'C7'}, {s:'S5', c:'C1'},
  {s:'S7', c:'C2'}, {s:'S7', c:'C3'}, {s:'S7', c:'C8'},
  {s:'S8', c:'C5'}, {s:'S11', c:'C12'}, {s:'S11', c:'C10'},
  {s:'S12', c:'C11'}, {s:'S13', c:'C6'}
] AS rel
MATCH (step:Step {step_id: rel.s}), (comp:Component {component_id: rel.c})
CREATE (step)-[:OPERATES_COMPONENT]->(comp);

// ---------- 18. 工序-质控点关系（HAS_QUALITY_CHECK）【您的原有设计，不变】 ----------
UNWIND [
  {s:'S3', q:'Q1'}, {s:'S3', q:'Q2'}, {s:'S3', q:'Q5'}, {s:'S3', q:'Q6'},
  {s:'S4', q:'Q4'}, {s:'S5', q:'Q4'}, {s:'S5', q:'Q5'},
  {s:'S6', q:'Q4'}, {s:'S6', q:'Q5'},
  {s:'S7', q:'Q7'}, {s:'S7', q:'Q8'}, {s:'S8', q:'Q8'},
  {s:'S11', q:'Q9'}, {s:'S11', q:'Q10'}, {s:'S11', q:'Q11'}, {s:'S11', q:'Q12'},
  {s:'S12', q:'Q11'},
  {s:'S13', q:'Q13'}, {s:'S13', q:'Q14'}, {s:'S13', q:'Q15'}, {s:'S13', q:'Q16'}, {s:'S13', q:'Q17'}, {s:'S13', q:'Q18'},
  {s:'S14', q:'Q19'}
] AS rel
MATCH (step:Step {step_id: rel.s}), (qc:QualityCheck {qc_id: rel.q})
CREATE (step)-[:HAS_QUALITY_CHECK]->(qc);

// ---------- 19. 工序-规范关系（FOLLOWS_STANDARD）【您的原有设计，不变】 ----------
UNWIND [
  {s:'S1', st:'ST1'}, {s:'S1', st:'ST2'}, {s:'S1', st:'ST4'},
  {s:'S3', st:'ST1'}, {s:'S3', st:'ST2'},
  {s:'S4', st:'ST1'},
  {s:'S5', st:'ST1'}, {s:'S5', st:'ST2'},
  {s:'S6', st:'ST2'},
  {s:'S7', st:'ST2'}, {s:'S7', st:'ST6'},
  {s:'S8', st:'ST1'}, {s:'S8', st:'ST2'},
  {s:'S11', st:'ST1'},
  {s:'S12', st:'ST1'},
  {s:'S13', st:'ST1'}, {s:'S13', st:'ST3'},
  {s:'S14', st:'ST1'}
] AS rel
MATCH (step:Step {step_id: rel.s}), (std:Standard {standard_id: rel.st})
CREATE (step)-[:FOLLOWS_STANDARD]->(std);

// ============================================
// 【新增】第四部分：V2.0 新增关系
// ============================================

// ---------- 【新增】20. WorkMethod → Process（CONTAINS_PROCESS） ----------
MATCH (wm:WorkMethod {method_id:'WM_CHENGTAISHENSHUI_001'})
MATCH (p:Process {process_id:'PROCESS_CHENGTAISHENSHUI_001'})
CREATE (wm)-[:CONTAINS_PROCESS]->(p);

// ---------- 【新增】21. WorkMethod → Project（APPLIED_IN） ----------
MATCH (wm:WorkMethod {method_id:'WM_CHENGTAISHENSHUI_001'})
MATCH (pr:Project) WHERE pr.project_id IN ['PRJ_CHENGTAISHENSHUI_001','PRJ_CHENGTAISHENSHUI_002']
CREATE (wm)-[:APPLIED_IN {effect:'良好'}]->(pr);

// ---------- 【新增】22. WorkMethod → GeoCondition（SUITABLE_FOR） ----------
MATCH (wm:WorkMethod {method_id:'WM_CHENGTAISHENSHUI_001'})
MATCH (g:GeoCondition) WHERE g.geo_id IN ['GEO_CHENGTAISHENSHUI_001','GEO_CHENGTAISHENSHUI_002']
CREATE (wm)-[:SUITABLE_FOR {match_degree:'核心适用', confidence:'高'}]->(g);

// ---------- 【新增】23. Process → ProcessParameter（HAS_PARAMETER） ----------
MATCH (p:Process {process_id:'PROCESS_CHENGTAISHENSHUI_001'})
MATCH (pp:ProcessParameter) WHERE pp.param_id IN ['PP_001','PP_002','PP_003','PP_004','PP_005','PP_006','PP_007','PP_008','PP_009','PP_010','PP_011','PP_012','PP_013','PP_014','PP_015']
CREATE (p)-[:HAS_PARAMETER]->(pp);

// ---------- 【新增】24. Step → ProcessParameter（STEP_HAS_PARAMETER） ----------
UNWIND [
  {s:'S3', p:'PP_001'}, {s:'S3', p:'PP_002'}, {s:'S3', p:'PP_011'},
  {s:'S4', p:'PP_003'}, {s:'S4', p:'PP_004'}, {s:'S4', p:'PP_012'},
  {s:'S7', p:'PP_014'},
  {s:'S8', p:'PP_015'},
  {s:'S9', p:'PP_013'},
  {s:'S13', p:'PP_005'}, {s:'S13', p:'PP_006'}, {s:'S13', p:'PP_007'}, {s:'S13', p:'PP_008'}, {s:'S13', p:'PP_009'},
  {s:'S14', p:'PP_010'}
] AS rel
MATCH (step:Step {step_id: rel.s}), (pp:ProcessParameter {param_id: rel.p})
CREATE (step)-[:STEP_HAS_PARAMETER]->(pp);

// ---------- 【新增】25. GeoCondition → Project（MATCHES_GEOLOGY） ----------
MATCH (g:GeoCondition {geo_id:'GEO_CHENGTAISHENSHUI_001'})
MATCH (pr:Project {project_id:'PRJ_CHENGTAISHENSHUI_002'})
CREATE (g)-[:MATCHES_GEOLOGY]->(pr);

// ============================================
// 第五部分：新增查询示例（基于增强后的图谱）
// ============================================

/*
【查询1】查询工法全貌（含经济效益）
MATCH (wm:WorkMethod {method_id:'WM_CHENGTAISHENSHUI_001'})-[:CONTAINS_PROCESS]->(p:Process)-[:CONTAINS_STEP]->(s:Step)
RETURN wm.method_name AS 工法名称,
       wm.method_level_name AS 级别,
       wm.completion_unit AS 完成单位,
       wm.economic_benefit_saving AS 节省金额,
       wm.economic_benefit_unit_cost_this AS 本工法单价,
       wm.economic_benefit_unit_cost_alt AS 替代方案单价,
       count(s) AS 工序数量

【查询2】地质条件→推荐工法
MATCH (g:GeoCondition {name:'深水河床砂卵石覆盖层'})<-[:SUITABLE_FOR]-(wm:WorkMethod)
RETURN wm.method_name AS 推荐工法,
       wm.method_level_name AS 级别,
       wm.applicable_scope_summary AS 适用范围

【查询3】参数超限预警（温控）
MATCH (p:Process)-[:HAS_PARAMETER]->(pp:ProcessParameter)
WHERE pp.alert_level IN ['warning','critical']
RETURN pp.name AS 参数名称,
       pp.threshold AS 阈值要求,
       pp.alert_level AS 告警级别
ORDER BY pp.alert_level DESC

【查询4】某工序所需全部资源（含数量）
MATCH (s:Step {name:'开挖与围檩支撑安装交替进行'})
OPTIONAL MATCH (s)-[ue:USES_EQUIPMENT]->(e:Equipment)
OPTIONAL MATCH (s)-[um:USES_MATERIAL]->(m:Material)
OPTIONAL MATCH (s)-[:OPERATES_COMPONENT]->(c:Component)
RETURN s.name AS 工序,
       collect(DISTINCT e.name + ' ' + ue.quantity) AS 设备清单,
       collect(DISTINCT m.name + ' ' + um.quantity) AS 材料清单,
       collect(DISTINCT c.name) AS 构件清单

【查询5】规范废止检查
MATCH (st:Standard)
WHERE st.status = 'active' AND st.superseded_by <> ''
RETURN st.code AS 规范编号,
       st.name AS 规范名称,
       st.superseded_by AS 已被替代,
       'WARNING: 该规范已被新标准替代，引用此规范的工法需要更新' AS 提醒
*/
