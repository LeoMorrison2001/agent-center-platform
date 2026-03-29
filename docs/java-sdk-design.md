# Java SDK Design

本文档用于说明如何在 Java 微服务项目中封装并接入当前智能体平台的调用 SDK。

目标：

- 让业务模块不直接手写 HTTP 请求
- 让业务模块不直接处理 `task_id`
- 把“提交任务 + 轮询结果 + 超时处理”统一封装
- 让心理报告、干预方案等业务模块直接调用 `call()`

## Design Goal

业务代码最终尽量做到：

```java
String result = agentPlatformClient.call("intervention_plan", promptJson);
```

或者：

```java
String result = agentPlatformClient.call("intervention_plan", promptObject);
```

业务侧不需要关心：

- `/api/platform/dispatch` 的 HTTP 细节
- `task_id` 的保存与查询
- 轮询 `/api/platform/logs/{task_id}`
- 超时与失败状态判断

这些逻辑应全部下沉到 SDK 内部。

## Recommended Module

如果当前 Java 项目是 Maven 多模块微服务，建议新建一个公共模块，例如：

```text
framework-agent-platform
```

可放在现有 `framework` 或 `common` 层中，由其他业务模块引入。

推荐结构：

```text
framework-agent-platform
├─ pom.xml
└─ src/main/java/com/yourcompany/framework/agent/
   ├─ config/
   │  ├─ AgentPlatformProperties.java
   │  └─ AgentPlatformAutoConfiguration.java
   ├─ client/
   │  ├─ AgentPlatformClient.java
   │  └─ DefaultAgentPlatformClient.java
   ├─ model/
   │  ├─ DispatchRequest.java
   │  ├─ DispatchResponse.java
   │  ├─ TaskLogResponse.java
   │  ├─ TaskStatus.java
   │  └─ CallResult.java
   ├─ exception/
   │  ├─ AgentPlatformException.java
   │  ├─ AgentTaskFailedException.java
   │  └─ AgentTaskTimeoutException.java
   └─ support/
      └─ JsonSupport.java
```

## Recommended Dependencies

如果你们是 Spring Boot 项目，第一版建议尽量简单：

- Spring Web
- Jackson
- Spring Boot Configuration Processor

如果项目已经统一使用以下技术，也可以直接复用：

- `RestClient`
- `WebClient`
- `OpenFeign`

第一版更推荐：

- `RestClient` 或 `WebClient`
- Jackson

## Platform APIs Used by SDK

SDK 内部主要依赖以下平台接口：

- `POST /api/platform/dispatch`
- `GET /api/platform/logs/{task_id}`

当前平台任务状态统一为：

- `queued`
- `completed`
- `failed`

## Core SDK Interface

建议先定义一个稳定的客户端接口：

```java
public interface AgentPlatformClient {

    String dispatch(String agentKey, String taskContent);

    <T> String dispatch(String agentKey, T payload);

    TaskLogResponse getTask(String taskId);

    String call(String agentKey, String taskContent);

    String call(String agentKey, String taskContent, Duration timeout);

    <T> String call(String agentKey, T payload);

    <T> String call(String agentKey, T payload, Duration timeout);

    CallResult callWithMetadata(String agentKey, String taskContent, Duration timeout);
}
```

建议原则：

- `dispatch()` 暴露低层异步能力
- `call()` 暴露高层同步能力
- `callWithMetadata()` 适合需要拿到 `task_id` 做追踪的高级场景

## Recommended Models

### DispatchRequest

```java
public class DispatchRequest {
    private String agentKey;
    private String taskContent;
}
```

### DispatchResponse

```java
public class DispatchResponse {
    private String taskId;
    private String agentKey;
    private String status;
    private String message;
}
```

### TaskLogResponse

```java
public class TaskLogResponse {
    private Long id;
    private String taskId;
    private String agentKey;
    private String instanceId;
    private String taskContent;
    private String status;
    private String result;
    private String errorMessage;
    private String createdAt;
    private String startedAt;
    private String completedAt;
    private Integer durationMs;
}
```

### CallResult

```java
public class CallResult {
    private String taskId;
    private String agentKey;
    private String status;
    private String result;
    private Integer durationMs;
}
```

## Configuration

建议统一配置：

```yaml
agent:
  platform:
    base-url: http://agent-platform:3150
    default-timeout: 20s
    poll-interval: 500ms
```

对应配置类：

```java
@ConfigurationProperties(prefix = "agent.platform")
public class AgentPlatformProperties {
    private String baseUrl;
    private Duration defaultTimeout = Duration.ofSeconds(20);
    private Duration pollInterval = Duration.ofMillis(500);
}
```

## Core Call Flow

`call()` 内部建议按以下流程实现：

1. 调用 `/api/platform/dispatch`
2. 获取 `task_id`
3. 进入轮询循环
4. 周期性调用 `/api/platform/logs/{task_id}`
5. 根据状态处理：
   - `queued`: 继续等待
   - `completed`: 返回结果
   - `failed`: 抛出失败异常
6. 超时则抛出超时异常

伪代码：

```java
public String call(String agentKey, String taskContent, Duration timeout) {
    DispatchResponse dispatch = dispatchInternal(agentKey, taskContent);
    String taskId = dispatch.getTaskId();

    long deadline = System.currentTimeMillis() + timeout.toMillis();

    while (System.currentTimeMillis() < deadline) {
        TaskLogResponse task = getTask(taskId);

        if ("completed".equals(task.getStatus())) {
            return task.getResult();
        }

        if ("failed".equals(task.getStatus())) {
            throw new AgentTaskFailedException(taskId, task.getErrorMessage());
        }

        sleep(properties.getPollInterval());
    }

    throw new AgentTaskTimeoutException(taskId, timeout);
}
```

## JSON Payload Recommendation

对于心理报告、干预方案这类场景，推荐直接传 JSON。

SDK 可以支持：

```java
String result = client.call("intervention_plan", promptObject);
```

内部自动序列化：

```java
String payload = objectMapper.writeValueAsString(promptObject);
```

推荐传入结构化 JSON，而不是完全依赖自然语言拼接。

例如：

```json
{
  "instruction": "请基于以下心理测评结果生成干预方案",
  "report_data": {
    "report_id": "r123",
    "scale_type": "SCL-90",
    "risk_level": "medium",
    "scores": {
      "depression": 78,
      "anxiety": 65
    }
  },
  "output_requirements": {
    "language": "zh-CN",
    "style": "professional"
  }
}
```

## Exception Strategy

建议定义至少三类异常：

### AgentPlatformException

基础异常，表示平台调用失败。

### AgentTaskFailedException

任务执行失败，通常对应平台任务状态 `failed`。

建议包含：

- `taskId`
- `errorMessage`

### AgentTaskTimeoutException

任务在指定超时时间内未完成。

建议包含：

- `taskId`
- `timeout`

## Logging Recommendation

虽然业务层可以不关心 `task_id`，但 SDK 内部日志建议保留：

- `agent_key`
- `task_id`
- `status`
- 耗时

这样后续排查平台调用问题会非常方便。

## Business Usage Recommendation

在心理报告场景中，建议业务后端不要同步阻塞前端请求。

推荐流程：

1. 前端提交答题结果
2. 后端完成算分
3. 后端先保存基础报告
4. 后端启动后台任务
5. 后台任务中调用：

```java
String plan = agentPlatformClient.call("intervention_plan", promptJson);
```

6. 拿到结果后更新报告表
7. 前端通过 `reportId` 轮询自己业务系统的报告接口

这样业务模块只依赖 SDK，不直接关心平台任务细节。

## First Version Scope

建议第一版只做这些能力：

1. `dispatch`
2. `getTask`
3. `call`
4. Java 对象自动转 JSON
5. 超时控制
6. 失败异常抛出

先不要一开始就做：

- 回调模式
- WebSocket 订阅
- 批量调用
- 自动重试
- Starter 复杂扩展点

把最小闭环先做稳。

## Future Enhancements

后续如果有需要，可以继续扩展：

- `callForObject()`：自动把结果反序列化成对象
- `callAsync()`：返回 `CompletableFuture`
- 回调 / Webhook 模式
- traceId 透传
- 限流与熔断
- Spring Boot Starter 自动装配

## Suggested Implementation Order

明天实现时建议按这个顺序来：

1. 定义 DTO 和异常类
2. 定义 `AgentPlatformClient` 接口
3. 完成 `dispatch()` 和 `getTask()`
4. 完成 `call()` 的轮询逻辑
5. 增加对象转 JSON 的重载
6. 在一个实际业务模块里接入验证

## Summary

这套 Java SDK 的目标不是暴露平台所有细节，而是把平台当前的异步任务模型封装成业务友好的同步调用模型。

最终业务代码应尽量接近：

```java
String result = agentPlatformClient.call("intervention_plan", promptObject);
```

这样调用方不需要手写 HTTP、也不需要自己处理 `task_id` 和轮询逻辑。
