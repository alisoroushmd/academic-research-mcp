import Foundation

/// A message in the chat conversation, displayed in the UI.
struct ChatMessage: Identifiable {
    let id = UUID()
    let role: ChatRole
    let content: String
    let timestamp: Date
    var toolCalls: [ToolCallInfo]

    init(role: ChatRole, content: String, toolCalls: [ToolCallInfo] = []) {
        self.role = role
        self.content = content
        self.timestamp = Date()
        self.toolCalls = toolCalls
    }
}

enum ChatRole {
    case user
    case assistant
    case system
}

/// Tracks a tool call and its result for display in the UI.
struct ToolCallInfo: Identifiable {
    let id = UUID()
    let toolName: String
    let input: String
    var status: ToolCallStatus
    var resultSummary: String

    init(toolName: String, input: String) {
        self.toolName = toolName
        self.input = input
        self.status = .running
        self.resultSummary = ""
    }
}

enum ToolCallStatus {
    case running
    case completed
    case failed
}
