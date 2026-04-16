import SwiftUI

/// App settings — API source info and about section.
struct SettingsView: View {
    var body: some View {
        NavigationStack {
            List {
                Section("Data Sources") {
                    SourceInfoRow(
                        name: "OpenAlex",
                        detail: "250M+ works, highest throughput, no auth needed",
                        color: .orange
                    )
                    SourceInfoRow(
                        name: "Semantic Scholar",
                        detail: "Citation graphs, recommendations, author metrics",
                        color: .purple
                    )
                    SourceInfoRow(
                        name: "PubMed",
                        detail: "Clinical/biomedical literature, MeSH terms",
                        color: .teal
                    )
                }

                Section("Search Tips") {
                    TipRow(
                        icon: "magnifyingglass",
                        text: "Use specific terms for better results. Try topic + methodology."
                    )
                    TipRow(
                        icon: "line.3.horizontal.decrease.circle",
                        text: "Filter by year range, source, or open access availability."
                    )
                    TipRow(
                        icon: "bookmark",
                        text: "Bookmark papers to build your reading list offline."
                    )
                    TipRow(
                        icon: "arrow.triangle.branch",
                        text: "Tap a paper to explore its citation network and find related work."
                    )
                }

                Section("About") {
                    LabeledContent("Version", value: "1.0.0")
                    LabeledContent("Platform", value: "iOS 17+")
                    LabeledContent("Data", value: "Live from academic APIs")
                }

                Section {
                    Text("This app queries academic APIs directly. No API keys are required for basic use. Results are not cached between sessions.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Settings")
        }
    }
}

private struct SourceInfoRow: View {
    let name: String
    let detail: String
    let color: Color

    var body: some View {
        HStack {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct TipRow: View {
    let icon: String
    let text: String

    var body: some View {
        Label(text, systemImage: icon)
            .font(.caption)
    }
}
