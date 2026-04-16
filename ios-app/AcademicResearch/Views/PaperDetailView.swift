import SwiftUI
import SwiftData

/// Full detail view for a single paper with abstract, metadata, citations, and actions.
struct PaperDetailView: View {
    let paper: Paper

    @State private var viewModel: PaperDetailViewModel
    @State private var bookmarksVM = BookmarksViewModel()
    @Environment(\.modelContext) private var modelContext
    @Environment(\.openURL) private var openURL

    init(paper: Paper) {
        self.paper = paper
        _viewModel = State(initialValue: PaperDetailViewModel(paper: paper))
    }

    var body: some View {
        List {
            // Header
            Section {
                VStack(alignment: .leading, spacing: 10) {
                    Text(paper.title)
                        .font(.title3)
                        .fontWeight(.bold)

                    Text(paper.authors.joined(separator: ", "))
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    HStack(spacing: 16) {
                        if let year = paper.year {
                            Label(String(year), systemImage: "calendar")
                        }
                        Label("\(paper.citationCount) citations", systemImage: "quote.bubble")
                        SourceBadge(source: paper.source)
                    }
                    .font(.caption)
                }
            }

            // Abstract
            if !paper.abstract.isEmpty {
                Section("Abstract") {
                    Text(paper.abstract)
                        .font(.subheadline)
                        .textSelection(.enabled)
                }
            }

            // Metadata
            Section("Details") {
                if !paper.venue.isEmpty {
                    LabeledRow(label: "Venue", value: paper.venue)
                }
                if !paper.doi.isEmpty {
                    LabeledRow(label: "DOI", value: paper.doi)
                }
                if !paper.pmid.isEmpty {
                    LabeledRow(label: "PMID", value: paper.pmid)
                }
                if !paper.arxivID.isEmpty {
                    LabeledRow(label: "arXiv", value: paper.arxivID)
                }
            }

            // Actions
            Section("Actions") {
                Button {
                    bookmarksVM.toggleBookmark(paper, in: modelContext)
                } label: {
                    Label(
                        bookmarksVM.isBookmarked(paper, in: modelContext) ? "Remove Bookmark" : "Bookmark",
                        systemImage: bookmarksVM.isBookmarked(paper, in: modelContext)
                            ? "bookmark.fill" : "bookmark"
                    )
                }

                if let url = paper.doiURL {
                    Button {
                        openURL(url)
                    } label: {
                        Label("Open via DOI", systemImage: "safari")
                    }
                }

                if let url = paper.openAccessPDFURL {
                    Button {
                        openURL(url)
                    } label: {
                        Label("Open Access PDF", systemImage: "doc.richtext")
                    }
                }

                ShareLink(item: paper.doiURL ?? URL(string: "https://scholar.google.com/scholar?q=\(paper.title.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")")!) {
                    Label("Share", systemImage: "square.and.arrow.up")
                }
            }

            // Citations
            Section {
                DisclosureGroup("Cited By (\(viewModel.citations.count))") {
                    if viewModel.isLoadingCitations {
                        ProgressView()
                    } else if viewModel.citations.isEmpty {
                        Text("No citations loaded")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(viewModel.citations) { cited in
                            NavigationLink(value: cited) {
                                PaperRowView(paper: cited)
                            }
                        }
                    }
                }
            }
            .task { await viewModel.loadCitations() }

            // References
            Section {
                DisclosureGroup("References (\(viewModel.references.count))") {
                    if viewModel.isLoadingReferences {
                        ProgressView()
                    } else if viewModel.references.isEmpty {
                        Text("No references loaded")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(viewModel.references) { ref in
                            NavigationLink(value: ref) {
                                PaperRowView(paper: ref)
                            }
                        }
                    }
                }
            }
            .task { await viewModel.loadReferences() }

            // Recommendations
            if !viewModel.recommendations.isEmpty {
                Section("Similar Papers") {
                    ForEach(viewModel.recommendations) { rec in
                        NavigationLink(value: rec) {
                            PaperRowView(paper: rec)
                        }
                    }
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle("Paper")
        .navigationBarTitleDisplayMode(.inline)
        .navigationDestination(for: Paper.self) { paper in
            PaperDetailView(paper: paper)
        }
        .task { await viewModel.loadRecommendations() }
    }
}

/// A simple label-value row for metadata display.
struct LabeledRow: View {
    let label: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.subheadline)
                .textSelection(.enabled)
        }
    }
}
