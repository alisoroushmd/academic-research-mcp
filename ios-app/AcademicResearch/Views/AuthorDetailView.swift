import SwiftUI

/// Detail view for an author profile, showing metadata and publications.
struct AuthorDetailView: View {
    let author: Author
    @State private var viewModel = AuthorViewModel()

    var body: some View {
        List {
            // Profile header
            Section {
                VStack(alignment: .leading, spacing: 8) {
                    Text(author.name)
                        .font(.title2)
                        .fontWeight(.bold)

                    if !author.affiliation.isEmpty {
                        Label(author.affiliation, systemImage: "building.2")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }

                    HStack(spacing: 20) {
                        StatView(label: "Works", value: "\(author.worksCount)")
                        StatView(label: "Citations", value: formatCount(author.citationCount))
                        if let h = author.hIndex {
                            StatView(label: "h-index", value: "\(h)")
                        }
                    }
                    .padding(.top, 4)
                }
            }

            // Publications
            Section("Publications") {
                if viewModel.isLoadingPapers {
                    ProgressView("Loading publications...")
                } else if viewModel.authorPapers.isEmpty {
                    Text("No publications loaded")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(viewModel.authorPapers) { paper in
                        NavigationLink(value: paper) {
                            PaperRowView(paper: paper)
                        }
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Author")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(for: Paper.self) { paper in
            PaperDetailView(paper: paper)
        }
        .task {
            await viewModel.loadAuthorPapers(author: author)
        }
    }

    private func formatCount(_ n: Int) -> String {
        if n >= 1_000_000 { return String(format: "%.1fM", Double(n) / 1_000_000) }
        if n >= 1_000 { return String(format: "%.1fK", Double(n) / 1_000) }
        return "\(n)"
    }
}

struct StatView: View {
    let label: String
    let value: String

    var body: some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.headline)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
    }
}
