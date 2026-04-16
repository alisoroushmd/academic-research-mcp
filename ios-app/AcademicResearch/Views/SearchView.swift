import SwiftUI

/// Main search screen — the primary entry point of the app.
struct SearchView: View {
    @State private var viewModel = SearchViewModel()

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

                if viewModel.papers.isEmpty && viewModel.state == .idle {
                    ContentUnavailableView(
                        "Search Academic Papers",
                        systemImage: "doc.text.magnifyingglass",
                        description: Text("Search across OpenAlex, Semantic Scholar, and PubMed.\nOver 250 million works available.")
                    )
                } else if viewModel.papers.isEmpty && !viewModel.state.isSearching {
                    ContentUnavailableView.search(text: viewModel.query)
                } else {
                    Section {
                        ForEach(viewModel.papers) { paper in
                            NavigationLink(value: paper) {
                                PaperRowView(paper: paper)
                            }
                        }
                    } header: {
                        if case .loaded(let count) = viewModel.state {
                            Text("\(count) results")
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .navigationTitle("Search")
            .navigationDestination(for: Paper.self) { paper in
                PaperDetailView(paper: paper)
            }
            .searchable(
                text: $viewModel.query,
                placement: .navigationBarDrawer(displayMode: .always),
                prompt: "Search papers, authors, topics..."
            )
            .onSubmit(of: .search) {
                viewModel.search()
            }
            .overlay {
                if viewModel.state.isSearching {
                    ProgressView("Searching...")
                        .padding()
                        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                }
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        viewModel.showFilters = true
                    } label: {
                        Image(systemName: hasActiveFilters ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
                    }
                }
            }
            .sheet(isPresented: $viewModel.showFilters) {
                FilterSheet(filters: $viewModel.filters)
            }
        }
    }

    private var hasActiveFilters: Bool {
        viewModel.filters.source != nil
            || !viewModel.filters.yearFrom.isEmpty
            || !viewModel.filters.yearTo.isEmpty
            || viewModel.filters.openAccessOnly
            || viewModel.filters.sortBy != .relevance
    }
}
