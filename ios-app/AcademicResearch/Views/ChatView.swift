import SwiftUI

/// Conversational interface where the user chats with Claude, which orchestrates
/// academic tool calls and synthesizes research findings.
struct ChatView: View {
    @State private var viewModel = ChatViewModel()
    @FocusState private var isInputFocused: Bool

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Messages
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            if viewModel.messages.isEmpty {
                                WelcomeView()
                                    .padding(.top, 40)
                            }

                            ForEach(viewModel.messages) { message in
                                MessageBubble(message: message)
                                    .id(message.id)
                            }

                            if viewModel.isProcessing {
                                ThinkingIndicator()
                                    .id("thinking")
                            }
                        }
                        .padding(.horizontal)
                        .padding(.bottom, 8)
                    }
                    .onChange(of: viewModel.messages.count) {
                        withAnimation {
                            if let last = viewModel.messages.last {
                                proxy.scrollTo(last.id, anchor: .bottom)
                            } else if viewModel.isProcessing {
                                proxy.scrollTo("thinking", anchor: .bottom)
                            }
                        }
                    }
                }

                Divider()

                // Input bar
                HStack(alignment: .bottom, spacing: 8) {
                    TextField("Ask about papers, authors, topics...", text: $viewModel.inputText, axis: .vertical)
                        .lineLimit(1...5)
                        .textFieldStyle(.plain)
                        .focused($isInputFocused)
                        .onSubmit { sendMessage() }

                    Button(action: sendMessage) {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.title2)
                            .foregroundStyle(canSend ? .accent : .gray)
                    }
                    .disabled(!canSend)
                }
                .padding(.horizontal)
                .padding(.vertical, 10)
                .background(.bar)
            }
            .navigationTitle("Research Assistant")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button(role: .destructive) {
                            viewModel.clearConversation()
                        } label: {
                            Label("Clear Chat", systemImage: "trash")
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
        }
    }

    private var canSend: Bool {
        !viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && !viewModel.isProcessing
    }

    private func sendMessage() {
        guard canSend else { return }
        isInputFocused = false
        viewModel.send()
    }
}

// MARK: - Message Bubble

private struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        switch message.role {
        case .user:
            HStack {
                Spacer(minLength: 60)
                Text(message.content)
                    .font(.subheadline)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(.accent.opacity(0.15))
                    .clipShape(RoundedRectangle(cornerRadius: 16))
            }

        case .assistant:
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(message.content)
                        .font(.subheadline)
                        .textSelection(.enabled)
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 10)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 16))
                Spacer(minLength: 40)
            }

        case .system:
            if !message.toolCalls.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(message.toolCalls) { tool in
                        ToolCallRow(tool: tool)
                    }
                }
                .padding(.leading, 8)
            } else if !message.content.isEmpty {
                Text(message.content)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 6)
                    .frame(maxWidth: .infinity, alignment: .center)
            }
        }
    }
}

// MARK: - Tool Call Row

private struct ToolCallRow: View {
    let tool: ToolCallInfo

    var body: some View {
        HStack(spacing: 8) {
            Group {
                switch tool.status {
                case .running:
                    ProgressView()
                        .controlSize(.small)
                case .completed:
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                case .failed:
                    Image(systemName: "xmark.circle.fill")
                        .foregroundStyle(.red)
                }
            }
            .frame(width: 18)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 4) {
                    Text(tool.toolName)
                        .fontWeight(.medium)
                    if !tool.input.isEmpty {
                        Text(tool.input)
                            .foregroundStyle(.secondary)
                    }
                }
                .font(.caption)

                if !tool.resultSummary.isEmpty {
                    Text(tool.resultSummary)
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .background(Color(.tertiarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

// MARK: - Welcome View

private struct WelcomeView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "text.book.closed")
                .font(.system(size: 40))
                .foregroundStyle(.accent)

            Text("Research Assistant")
                .font(.title2)
                .fontWeight(.bold)

            Text("Ask questions about academic literature. I'll search across OpenAlex, Semantic Scholar, and PubMed to find and synthesize relevant papers.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            VStack(alignment: .leading, spacing: 8) {
                SuggestionChip(text: "What are the latest papers on transformer architectures?")
                SuggestionChip(text: "Find papers by Yoshua Bengio on deep learning")
                SuggestionChip(text: "What cites the original attention paper?")
            }
            .padding(.top, 8)
        }
        .padding(.horizontal, 32)
    }
}

private struct SuggestionChip: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.caption)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color(.tertiarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Thinking Indicator

private struct ThinkingIndicator: View {
    @State private var dotCount = 0

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: "sparkles")
                .foregroundStyle(.accent)
                .font(.caption)
            Text("Thinking" + String(repeating: ".", count: dotCount))
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .onAppear {
            Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { _ in
                dotCount = (dotCount + 1) % 4
            }
        }
    }
}
