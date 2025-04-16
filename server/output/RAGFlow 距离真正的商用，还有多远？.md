# RAGFlow 距离真正的商用，还有多远？  

经过各种维度的横向评估，最终我们选择了 RAGFlow 作为我们企业知识库的方案。从 Dify、MaxKB、FastGPT、QAnything 等竞品中，我们为什么选择了 RAGFlow？  

1. Quality in, quality out：我们支持官方提出的「Quality in, quality out」理念，我们技术和产品团队是做埋点出身的，深刻的了解到数据源的质量对后续的数据分析以及运营带来的深刻影响。数据源质量堪忧会带来后续数据维护极大的成本，比如标注、打标签、校准之类的人力成本。RAGFlow 在文档解析层面横向来看是最好的，也许有同学会提出完全可以用三方 API 来实现该效果，我们得考虑另一个问题，大多数企业知识库应用场景一定是本地化私有的，在纯离线场景下，RAGFlow 文档解析我们实测过比其他开源模型好很多。  

2. 开放性：一款开源产品一定是无法直接应用到生产环境，所以不可避免的我们需要基于 RAGFlow进行二开，此时源码的开发性至关重要。这里的开放性有两个层面：源码开放协议以及 Open API设计。  

a. 截止目前为止 RAGFlow 仍然是 Apache-2.0 license ，相关于其他竞品不同程度的限制，RAGFlow 表现的相当开放，在这里再次感谢 RAGFlow 官方的开源精神。  
b. Open API ，RAGFlow 提供了相对完整的对外 API ，基于这些 API ，二开的难度极大的降低且具备极大的灵活性  

Acompletereference forRAGFlow'sRESTfulAPl.Beforeproceeding,pleaseensureyouhaveyourRAGFlowAPlkeyreadyfor  

# OpenAl-Compatible API  

<html><body><table><tr><td>OpenAl-Compatible API</td></tr><tr><td>Create chat completion</td></tr><tr><td>DATASET MANAGEMENT</td></tr><tr><td>Create dataset</td></tr><tr><td>Delete datasets</td></tr><tr><td>Update dataset</td></tr><tr><td>List datasets</td></tr><tr><td>FILE MANAGEMENT WITHIN DATASET</td></tr><tr><td>Upload documents</td></tr><tr><td>Update document</td></tr><tr><td>Download document</td></tr><tr><td>List documents</td></tr><tr><td>Delete documents</td></tr><tr><td>Parse documents</td></tr><tr><td>Stop parsing documents</td></tr><tr><td>CHUNK MANAGEMENT WITHIN DATASET</td></tr><tr><td>Add chunk</td></tr><tr><td>List chunks</td></tr><tr><td>Delete chunks</td></tr><tr><td>Update chunk</td></tr><tr><td>Retrieve chunks</td></tr><tr><td>CHAT ASSISTANT MANAGEMENT</td></tr><tr><td>Create chat assistant</td></tr><tr><td>Update chat assistant</td></tr><tr><td>Delete chat assistants</td></tr><tr><td></td></tr><tr><td>List chat assistants</td></tr></table></body></html>  

# Create chat completion  

POST/api/v1/chats_openai/{chat_id}/chat/completions  

Creates a model response for a given chat conversation.  

This APfollowsthesamerequestandresponseformatasOpenAl'sAPl.Itllowsyoutointeractwiththemodelinamanner similar to how you would with OpenAl's APl.  

# Request  

·Method:POST   
·URL:/api/v1/chats_openai/{chat_id}/chat/completions   
·Headers: content-Type:application/json' 0 Authorization: Bearer <YouR_API_KEY>  

那么，RAGFlow 要真正的落地到企业应用，产品功能层面还缺少哪些？这些天我们深入的和不同行业意见领袖做了深入交流，收获满满，我们将从真正企业应用视角来看，一款成熟的企业知识库产品该  

具备的能力。  

# 企业级知识库管理核心功能  

我们先参考下 FastGPT 商业版本功能：  

<html><body><table><tr><td></td><td>开源版</td><td>商业版</td><td>线上版</td></tr><tr><td>应用管理与高级编排</td><td>√</td><td></td><td>√</td></tr><tr><td>文档知识库</td><td></td><td>√</td><td>√</td></tr><tr><td>外部使用</td><td></td><td></td><td>√</td></tr><tr><td>API知识库</td><td></td><td></td><td>√</td></tr><tr><td>最大应用数量</td><td>500</td><td>无限制</td><td>由付费套餐决定</td></tr><tr><td>最大知识库数量 (单个知识库内容无限制)</td><td>30</td><td>无限制</td><td>由付费套餐决定</td></tr><tr><td>自定义版权信息</td><td>×</td><td></td><td>设计中</td></tr><tr><td>多租户与支付</td><td>×</td><td>√</td><td>√</td></tr><tr><td>团队空间&权限</td><td>×</td><td>√</td><td>√</td></tr><tr><td>应用发布安全配置</td><td>×</td><td>√</td><td></td></tr><tr><td>内容审核</td><td>×</td><td></td><td>√</td></tr><tr><td>web站点同步</td><td>×</td><td>√</td><td>√</td></tr><tr><td>主流文档库接入 (目前支持：语雀、飞书)</td><td>×</td><td></td><td>√</td></tr><tr><td>增强训练模式</td><td>×</td><td></td><td></td></tr><tr><td>第三方应用快速接入 (飞书、公众号)</td><td>×</td><td></td><td>√</td></tr><tr><td>管理后台</td><td>×</td><td></td><td>不需要</td></tr><tr><td>SSO 登录(可自定义，也可使用内置：Github、公众号、钉钉、谷歌等)</td><td>×</td><td></td><td>不需要</td></tr><tr><td>图片知识库</td><td>×</td><td>设计中</td><td>设计中</td></tr><tr><td>对话日志运营分析</td><td>×</td><td>设计中</td><td>设计中</td></tr><tr><td>完整商业授权</td><td>×</td><td></td><td></td></tr></table></body></html>  

可以看到商业版本核心的功能点：  

团队空间和权限管理  
Web 站点同步  
主流文档库接入  
三方应用接入  
SSO 登录  

QAnything 企业版本功能：  

• 高质量的文档解析：支持doc、ppt、xls更多文档格式的解析，针对docx、pptx、pdf做特别优化，支持准确的解析其中的表格和图片，且解析后多级标题的层级结构完整。  

• 更优的语义切分模型：提供最优的文本切分模型，按照层级标题及语义进行切分，自动处理导入的各种类型的数据，确保每个切片均包含完整的语义单元。  
• 更精准的问答：语义检索加混合检索，搜索召回率和命中率高。回答组织能力显著提升，能够清晰展示答案所依据的引用来源，答案支持带图片和表格。  
相对于基础版本，QAnything 企业版本聚焦于提升回答精准度，从文档解析、文本切分、回答图文混  
排进一步提升回答准确率。  

产品版本对比  


<html><body><table><tr><td></td><td>开源版</td><td>企业版</td></tr><tr><td>知识库</td><td></td><td></td></tr><tr><td>本地知识库管理</td><td>√</td><td>√</td></tr><tr><td>支持md、txt、pdf、jpg、png、jpeg、docx、xlsx、pptx、 eml、csv、网页链接等格式文件上传和解析</td><td>√</td><td>√</td></tr><tr><td>解析结果查看和编辑</td><td>√</td><td>√</td></tr><tr><td>知识库问答调试</td><td>√</td><td>√</td></tr><tr><td>支持doc、ppt、xls、jsonl格式文件上传和解析</td><td></td><td>√</td></tr><tr><td>支持解析docx和pptx中的表格和图片</td><td></td><td>√</td></tr><tr><td>支持解析pdf纯扫描版</td><td></td><td></td></tr><tr><td>markdown，pdf，docx，xlsx类型文件解析效果全面优化</td><td></td><td>√</td></tr><tr><td>更快的解析速度</td><td></td><td>√</td></tr><tr><td>上传文件时支持并行操作</td><td></td><td>√</td></tr><tr><td>问答集单独管理</td><td></td><td>√</td></tr><tr><td>支持添加文档标签以及基于标签的问答</td><td></td><td></td></tr></table></body></html>  

<html><body><table><tr><td colspan="3">Bot管理</td></tr><tr><td>设定角色及知识库</td><td>√</td><td>√</td></tr><tr><td>模型参数配置</td><td>√</td><td>√</td></tr><tr><td>Bot对话调试</td><td>√</td><td>√</td></tr><tr><td>发布到网页和企微</td><td>√</td><td>√</td></tr><tr><td>用户数据统计</td><td>√</td><td>√</td></tr><tr><td>大语言模型</td><td></td><td></td></tr><tr><td>支持对接主流大模型</td><td>√</td><td>√</td></tr><tr><td>针对Qwen2.5系列模型独立优化</td><td></td><td>√</td></tr><tr><td>RAG</td><td></td><td></td></tr><tr><td>基于语义的切分逻辑优化</td><td></td><td>√</td></tr><tr><td>更优的Embedding模型</td><td></td><td>√</td></tr><tr><td>更优的Rerank模型</td><td></td><td>√</td></tr><tr><td>问答能力</td><td></td><td></td></tr><tr><td>通用知识库问答能力</td><td>√</td><td>√</td></tr><tr><td>精准引用来源定位，清晰展示答案所依据的引用来源</td><td></td><td>√</td></tr><tr><td>prompt自我认知优化</td><td></td><td>√</td></tr><tr><td>长文档问答能力</td><td></td><td>√</td></tr></table></body></html>  

我们调研了国内外企业知识库产品，总结了一下功能：  

<html><body><table><tr><td>分类</td><td>核心功能</td><td>描述</td></tr><tr><td>数据接入与管理</td><td>多数据源接入</td><td>支持数据库、文档、API、网页爬取等多种 数据源</td></tr><tr><td></td><td>数据预处理与清洗</td><td>OCR、格式转换、去重、标准化等</td></tr><tr><td></td><td>权限控制</td><td>基于角色（RBAC）和用户（ABAC）的访问 管理</td></tr><tr><td></td><td>版本管理</td><td>知识库内容的版本迭代、变更记录和回滚</td></tr><tr><td>向量索引与检索</td><td>高效向量化存储</td><td>基于FAlSS、Milvus、Weaviate、PGVector 实现索引</td></tr><tr><td></td><td>混合检索 (Hybrid Search)</td><td>结合关键词（BM25）、语义搜索、知识图 谱等</td></tr><tr><td></td><td></td><td></td></tr></table></body></html>  

<html><body><table><tr><td></td><td>在线增量更新</td><td>支持知识库实时或定期自动更新索引</td></tr><tr><td>生成增强（RAG）与问答能 力</td><td>上下文增强</td><td>支持CoT（Chain of Thought）、ToT (Tree of Thought)</td></tr><tr><td></td><td>多模态支持</td><td>支持文本、图片、音频等输入类型</td></tr><tr><td></td><td>工具调用 (Tool Use)</td><td>结合API（如 SQL、ERP、CRM）实现行动 能力</td></tr><tr><td></td><td>多轮对话记忆</td><td>结合RAG 进行更精准的问答</td></tr><tr><td></td><td>可插拔LLM引擎</td><td>支持OpenAl、Claude、Gemini、本地 Llama、Mistral</td></tr><tr><td>知识增强与结构化输出</td><td>知识图谱（Knowledge Graph)</td><td>构建企业内部知识图谱，提高问答准确性</td></tr><tr><td></td><td>结构化输出（Structured Output)</td><td>支持JSON、表格、代码生成</td></tr><tr><td></td><td>自定义Prompt 模板</td><td>支持RAG查询的Prompt预设、调整、AB 测试</td></tr><tr><td></td><td>摘要与报告生成</td><td>生成结构化摘要、结论、行动建议等</td></tr><tr><td>监控与优化</td><td>查询日志与可视化分析</td><td>统计用户查询、热点问题、知识库覆盖率</td></tr><tr><td></td><td>反馈机制</td><td>支持人工审核、点赞/踩、主动补充知识</td></tr><tr><td></td><td>模型微调与知识库优化</td><td>提供LoRA／SFT进行企业私有微调</td></tr><tr><td></td><td>多租户管理</td><td>支持SaaS 部署下的独立知识库</td></tr><tr><td>部署与集成</td><td>本地化部署</td><td>支持私有化部署，保障数据安全</td></tr><tr><td></td><td>API与 SDK支持</td><td>提供 RESTful APl、Python/JavaScript SDK</td></tr><tr><td></td><td>插件生态</td><td></td></tr></table></body></html>  

<html><body><table><tr><td></td><td></td><td>支持Notion、Slack、企业微信、飞书等集 成</td></tr><tr><td></td><td>LLM代理（Agent）扩展</td><td>可与 AutoGPT、LangChain、Llamalndex 结合</td></tr></table></body></html>  

# 距离企业商用 RAGFlow 产品还缺哪些  

集合竞品以及国内外 RAG 产品调研情况，以我们目前企业级 RAG 知识库和智能助手产品的认知，我们认为 RAGFlow 需要在现有产品能力基础上，做以下产品能力补充。  

# 用户权限管理  

参考 RBAC（基于角色访问控制） 和 ABAC（基于属性访问控制） 的行业标准设计方式。  

# 1. 用户角色  

<html><body><table><tr><td>色</td><td>权限描述</td></tr><tr><td>管理员 (Admin)</td><td>完整管理权限，包括用户、团队、知识库和应用管理</td></tr><tr><td>普通用户 (User)</td><td>只能查询和使用被授权的知识库</td></tr></table></body></html>  

# 2. 权限规则  

<html><body><table><tr><td>功能</td><td>管理员</td><td>普通用户</td></tr><tr><td>用户管理</td><td>创建/删除用户，分配角色</td><td>×</td></tr><tr><td>团队管理</td><td>创建/删除团队，邀请成员</td><td>×</td></tr><tr><td>知识库管理</td><td>创建/删除知识库，授权访问</td><td>×</td></tr><tr><td>知识库访问</td><td>访问所有知识库</td><td>√仅能访问被授权知识库</td></tr><tr><td>API使用</td><td>√可调用RAGAPI</td><td>√可调用RAGAPI（受权阳</td></tr></table></body></html>  

# 3. 业务逻辑  

◦ 管理员 可以管理用户、团队、知识库和 API 权限。  
◦ 普通用户 只能使用知识库，不可修改权限或管理团队。  
◦ 团队成员继承团队权限，即用户加入团队后，会自动获得该团队的知识库访问权限。  

# 产品原型设计重构  

<img src="https://www.knowflowchat.cn/minio/5a5978f01aa411f0b2e35225ee02e7da/3ae2a7e2bd0a84445f1f04a51341d2fdf333e25b79cebda3a19b72e6fb40cfa7.jpg" width="300" alt="图片">  
欢迎回来，tom今天我们要使用哪个知识库？  

了解 RAGFlow 的同学可能也知道，目前 RAGFlow 的产品体验比较简陋，无论是核心的聊天主页面还是知识库页面都比较难以下咽。在 RAGFlow 交流社区内提过不少想换一个 UI 界面的需求，有的想接入三方 Open UI 或者 Dify ，我们的结论是重构整个 UI 设计：基于 RAGFlow API 能力，我们在现有服务基础上，改写所有页面设计。  

<img src="https://www.knowflowchat.cn/minio/5a5978f01aa411f0b2e35225ee02e7da/c6d56a017bcda7f3f37318278c41bde9daaa1c640ae128fb78728981b77a2a76.jpg" width="300" alt="图片">  

同时增强结构化输出能力，如回答中支持图文混排、代码、表格等格式。  

# 行业化解决方案最佳实践  

现 RAGFlow 从产品体验上来说，问题回答速度较慢，配置项较多，如何平衡回答精准度以及速度，是一个系统性问题。我们基于实际客户行业化落地产品交付经验，提供了将近 $50+$ 参数配置优化解决方案，针对不同的行业进行体系化优化。比如是通义千问大模型好还是 DeepSeek 更合适？比如是本地模型需要 DeepSeek 32B 蒸馏版还是满血版本？比如分块固定多大比较合适等等。  

我们判断未来行业化的解决方案不断沉淀是 RAG 应用服务商的核心竞争壁垒，这里不仅是技术产品的不断演进，同样是解决方案在行业化里的不断深化，这样才能真正的将知识库管理变得更智能、更高效。  

# 总结  

2024 年有一个业界争论不休的议题：在大模型越来越聪明、上下文长度越来越长的趋势下，RAG 是不是要退出历史舞台？我的回答是恰恰相反：RAG 反而可能会随着技术的进步进一步演化，甚至在某些场景下变得更加重要。因为 RAG 有一些天然的特性是可以和大模型相辅相成的，如知识的时效性、减少计算和存储成本、知识安全可控。未来的趋势可能是 超长上下文 和 智能检索 双管齐下，以应对不同应用场景的需求，真正的给企业降本增效，进入 AI 时代。  

最后介绍下我们团队 KnowFlow：基于 RAGFlow 的专注于私有化部署的企业知识库服务商。欢迎关注公众号：「KnowFlow 企业知识库」，一起探索企业知识库的未来。  