import Foundation

/// Client for the Anthropic Messages API with tool-use support.
/// Implements the agentic loop: send message → receive tool calls → execute → feed back → repeat.
actor AnthropicService {
    private let session: URLSession
    private let baseURL = "https://api.anthropic.com/v1/messages"

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 120
        config.timeoutIntervalForResource = 300
        self.session = URLSession(configuration: config)
    }

    /// Send a conversation to Claude and get a response (may include tool calls).
    func sendMessage(
        apiKey: String,
        messages: [[String: Any]],
        tools: [[String: Any]],
        system: String
    ) async throws -> ClaudeResponse {
        guard !apiKey.isEmpty else {
            throw AnthropicError.missingAPIKey
        }

        var request = URLRequest(url: URL(string: baseURL)!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")

        let body: [String: Any] = [
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
            "tools": tools
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw AnthropicError.networkError("Invalid response")
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            let body = String(data: data, encoding: .utf8) ?? ""
            if httpResponse.statusCode == 401 {
                throw AnthropicError.invalidAPIKey
            }
            if httpResponse.statusCode == 429 {
                throw AnthropicError.rateLimited
            }
            throw AnthropicError.httpError(code: httpResponse.statusCode, body: body)
        }

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw AnthropicError.decodingError("Invalid JSON")
        }

        return ClaudeResponse(from: json)
    }
}

// MARK: - Response Types

struct ClaudeResponse {
    let stopReason: String
    let content: [ContentBlock]

    var hasToolUse: Bool {
        content.contains { if case .toolUse = $0 { return true } else { return false } }
    }

    var textContent: String {
        content.compactMap {
            if case .text(let t) = $0 { return t } else { return nil }
        }.joined(separator: "\n")
    }

    var toolCalls: [ToolCall] {
        content.compactMap {
            if case .toolUse(let call) = $0 { return call } else { return nil }
        }
    }

    /// Serialize content blocks back to the API format for the conversation history.
    var contentJSON: [[String: Any]] {
        content.map { block in
            switch block {
            case .text(let text):
                return ["type": "text", "text": text]
            case .toolUse(let call):
                return ["type": "tool_use", "id": call.id, "name": call.name, "input": call.input]
            }
        }
    }

    init(from json: [String: Any]) {
        self.stopReason = json["stop_reason"] as? String ?? ""
        let rawContent = json["content"] as? [[String: Any]] ?? []
        self.content = rawContent.compactMap { block -> ContentBlock? in
            let type = block["type"] as? String ?? ""
            switch type {
            case "text":
                return .text(block["text"] as? String ?? "")
            case "tool_use":
                return .toolUse(ToolCall(
                    id: block["id"] as? String ?? "",
                    name: block["name"] as? String ?? "",
                    input: block["input"] as? [String: Any] ?? [:]
                ))
            default:
                return nil
            }
        }
    }
}

enum ContentBlock {
    case text(String)
    case toolUse(ToolCall)
}

struct ToolCall {
    let id: String
    let name: String
    let input: [String: Any]
}

// MARK: - Errors

enum AnthropicError: LocalizedError {
    case missingAPIKey
    case invalidAPIKey
    case rateLimited
    case networkError(String)
    case httpError(code: Int, body: String)
    case decodingError(String)

    var errorDescription: String? {
        switch self {
        case .missingAPIKey:
            return "Please set your Anthropic API key in Settings."
        case .invalidAPIKey:
            return "Invalid API key. Check your key in Settings."
        case .rateLimited:
            return "Rate limited. Please wait a moment."
        case .networkError(let msg):
            return "Network error: \(msg)"
        case .httpError(let code, _):
            return "API error (HTTP \(code))"
        case .decodingError(let msg):
            return "Decoding error: \(msg)"
        }
    }
}
