import SwiftUI

/// Search and browse author profiles across OpenAlex and Semantic Scholar.
struct AuthorSearchView: View {
    @State private var viewModel = AuthorViewModel()

    var body: some View {
        NavigationStack {
            List {
                if case .error(let message) = viewModel.state {
                    Section {
                        Label(message, systemImage: "exclamationmark.triangle")
                            .foregroundStyle(.red)
                            .font(.caption)
                    }
                }

                if viewModel.authors.isEmpty && viewModel.state == .idle {
                    ContentUnavailableView(
                        "Search Authors",
                        systemImage: "person.text.rectangle",
                        description: Text("Find researchers and view their publication profiles.")
                    )
                } else if viewModel.authors.isEmpty && !viewModel.state.isSearching {
                    ContentUnavailableView.search(text: viewModel.query)
                } else {
                    ForEach(viewModel.authors) { author in
                        NavigationLink(value: author) {
                            AuthorRowView(author: author)
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Authors")
            .navigationDestination(for: Author.self) { author in
                AuthorDetailView(author: author)
            }
            .searchable(
                text: $viewModel.query,
                placement: .navigationBarDrawer(displayMode: .always),
                prompt: "Search by author name..."
            )
            .onSubmit(of: .search) {
                viewModel.searchAuthors()
            }
            .overlay {
                if viewModel.state.isSearching {
                    ProgressView("Searching...")
                        .padding()
                        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                }
            }
        }
    }
}

struct AuthorRowView: View {
    let author: Author

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(author.name)
                .font(.subheadline)
                .fontWeight(.medium)

            if !author.affiliation.isEmpty {
                Text(author.affiliation)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            HStack(spacing: 12) {
                Label("\(author.worksCount) works", systemImage: "doc.text")
                Label("\(author.citationCount) citations", systemImage: "quote.bubble")
                if let h = author.hIndex {
                    Label("h-index \(h)", systemImage: "chart.bar")
                }
            }
            .font(.caption2)
            .foregroundStyle(.tertiary)

            SourceBadge(source: author.source)
        }
        .padding(.vertical, 2)
    }
}
