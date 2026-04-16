import Foundation
import SwiftUI

/// Orchestrates the conversation between the user, Claude, and academic API tools.
/// Implements the full agentic loop: user message → Claude → tool calls → execute → feed back → repeat.
@Observable
@MainActor
final class ChatViewModel {
    var messages: [ChatMessage] = []
    var inputText = ""
    var isProcessing = false
    var errorMessage: String?

    private let anthropic = AnthropicService()
    private var conversationHistory: [[String: Any]] = []

    private let systemPrompt = """
    You are an expert academic research assistant embedded in a mobile app. \
    You help researchers find papers, explore citation networks, discover authors, \
    and synthesize findings from the scientific literature.

    You have access to tools that search OpenAlex (250M+ works), Semantic Scholar \
    (citation graphs, recommendations), and PubMed (clinical/biomedical).

    Guidelines:
    - Use smart_search as your default search tool — it searches multiple sources.
    - Use find_paper to resolve specific DOIs, PMIDs, or titles.
    - Use get_paper_network to explore citation chains.
    - Use recommend_papers to find related work.
    - Summarize findings concisely. Cite papers by first author + year.
    - When presenting multiple papers, use a clear numbered list.
    - Be direct and scholarly in tone. Focus on what the user needs.
    """

    /// The maximum number of agentic loop iterations to prevent runaway tool calls.
    private let maxIterations = 10

    /// Send the user's message and run the agentic loop until Claude produces a final text response.
    func send() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }

        inputText = ""
        messages.append(ChatMessage(role: .user, content: text))
        conversationHistory.append(["role": "user", "content": text])
        errorMessage = nil

        isProcessing = true

        Task {
            defer { isProcessing = false }

            guard let apiKey = getAPIKey(), !apiKey.isEmpty else {
                errorMessage = "Please set your Anthropic API key in Settings."
                messages.append(ChatMessage(role: .system,
                    content: "Set your Anthropic API key in the Settings tab to start chatting."))
                return
            }

            do {
                try await runAgentLoop(apiKey: apiKey)
            } catch {
                errorMessage = error.localizedDescription
                messages.append(ChatMessage(role: .system, content: "Error: \(error.localizedDescription)"))
            }
        }
    }

    /// Clear the conversation and start fresh.
    func clearConversation() {
        messages = []
        conversationHistory = []
        errorMessage = nil
    }

    // MARK: - Agentic Loop

    private func runAgentLoop(apiKey: String) async throws {
        for _ in 0..<maxIterations {
            let response = try await anthropic.sendMessage(
                apiKey: apiKey,
                messages: conversationHistory,
                tools: ToolDefinitions.all,
                system: systemPrompt
            )

            if response.hasToolUse {
                // Add assistant's response (with tool_use blocks) to history
                conversationHistory.append([
                    "role": "assistant",
                    "content": response.contentJSON
                ])

                // Show any text Claude produced before tool calls
                let preText = response.textContent
                if !preText.isEmpty {
                    messages.append(ChatMessage(role: .assistant, content: preText))
                }

                // Execute each tool call and show progress
                var toolResultBlocks: [[String: Any]] = []

                for call in response.toolCalls {
                    // Show tool call in UI
                    let inputSummary = summarizeToolInput(call)
                    var toolInfo = ToolCallInfo(toolName: displayName(for: call.name), input: inputSummary)
                    let toolMessage = ChatMessage(role: .system, content: "", toolCalls: [toolInfo])
                    messages.append(toolMessage)
                    let toolMessageIndex = messages.count - 1

                    // Execute
                    let result = await ToolExecutor.execute(call)

                    // Update UI with result
                    toolInfo.status = result["error"] != nil ? .failed : .completed
                    toolInfo.resultSummary = summarizeToolResult(call.name, result)
                    messages[toolMessageIndex].toolCalls = [toolInfo]

                    // Serialize result for Claude
                    let resultJSON: String
                    if let data = try? JSONSerialization.data(withJSONObject: result),
                       let str = String(data: data, encoding: .utf8) {
                        resultJSON = str
                    } else {
                        resultJSON = "{\"error\": \"Failed to serialize result\"}"
                    }

                    toolResultBlocks.append([
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": resultJSON
                    ])
                }

                // Feed tool results back to Claude
                conversationHistory.append([
                    "role": "user",
                    "content": toolResultBlocks
                ])

                // Continue the loop — Claude may call more tools or produce final text
                continue

            } else {
                // Final text response — no more tool calls
                let text = response.textContent
                if !text.isEmpty {
                    messages.append(ChatMessage(role: .assistant, content: text))
                }
                conversationHistory.append([
                    "role": "assistant",
                    "content": text
                ])
                return
            }
        }

        messages.append(ChatMessage(role: .system, content: "Reached maximum tool iterations."))
    }

    // MARK: - Helpers

    private func getAPIKey() -> String? {
        UserDefaults.standard.string(forKey: "anthropic_api_key")
    }

    private func displayName(for toolName: String) -> String {
        switch toolName {
        case "smart_search": return "Searching papers"
        case "search_papers": return "Searching"
        case "find_paper": return "Finding paper"
        case "get_paper_network": return "Loading citations"
        case "recommend_papers": return "Finding recommendations"
        case "search_authors": return "Searching authors"
        case "get_author_works": return "Loading publications"
        case "open_access": return "Finding PDF"
        default: return toolName
        }
    }

    private func summarizeToolInput(_ call: ToolCall) -> String {
        if let query = call.input["query"] as? String {
            return "\"\(query)\""
        }
        if let id = call.input["identifier"] as? String {
            return id
        }
        if let id = call.input["paper_id"] as? String {
            return id.count > 40 ? String(id.prefix(40)) + "..." : id
        }
        if let doi = call.input["doi"] as? String {
            return doi
        }
        return ""
    }

    private func summarizeToolResult(_ toolName: String, _ result: [String: Any]) -> String {
        if let error = result["error"] as? String {
            return "Error: \(error)"
        }
        if let total = result["total"] as? Int {
            return "\(total) results"
        }
        if let papers = result["papers"] as? [[String: Any]] {
            return "\(papers.count) papers"
        }
        if let recs = result["recommendations"] as? [[String: Any]] {
            return "\(recs.count) recommendations"
        }
        if let title = result["title"] as? String {
            return title.count > 50 ? String(title.prefix(50)) + "..." : title
        }
        if result["is_open_access"] as? Bool == true {
            return "Open access link found"
        }
        return "Done"
    }
}
