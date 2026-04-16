import SwiftUI

/// Compact row for displaying a paper in a list.
struct PaperRowView: View {
    let paper: Paper

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(paper.title)
                .font(.subheadline)
                .fontWeight(.medium)
                .lineLimit(2)

            Text(paper.authorsDisplay)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(1)

            HStack(spacing: 12) {
                if let year = paper.year {
                    Label(String(year), systemImage: "calendar")
                }

                Label("\(paper.citationCount)", systemImage: "quote.bubble")

                if !paper.venue.isEmpty {
                    Text(paper.venue)
                        .lineLimit(1)
                }
            }
            .font(.caption2)
            .foregroundStyle(.tertiary)

            HStack(spacing: 6) {
                SourceBadge(source: paper.source)

                if paper.isOpenAccess {
                    Badge(text: "Open Access", color: .green)
                }

                if !paper.doi.isEmpty {
                    Badge(text: "DOI", color: .blue)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

/// Small colored badge.
struct Badge: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.system(size: 9, weight: .semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}

/// Source indicator badge.
struct SourceBadge: View {
    let source: PaperSource

    var body: some View {
        Badge(text: source.rawValue, color: sourceColor)
    }

    private var sourceColor: Color {
        switch source {
        case .openAlex: return .orange
        case .semanticScholar: return .purple
        case .pubMed: return .teal
        case .crossRef: return .indigo
        }
    }
}
