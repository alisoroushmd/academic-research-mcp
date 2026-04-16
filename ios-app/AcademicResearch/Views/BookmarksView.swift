import SwiftUI
import SwiftData

/// Displays the user's locally bookmarked papers.
struct BookmarksView: View {
    @Query(sort: \BookmarkedPaper.bookmarkedAt, order: .reverse)
    private var bookmarks: [BookmarkedPaper]

    @State private var bookmarksVM = BookmarksViewModel()
    @Environment(\.modelContext) private var modelContext

    var body: some View {
        NavigationStack {
            Group {
                if bookmarks.isEmpty {
                    ContentUnavailableView(
                        "No Bookmarks",
                        systemImage: "bookmark",
                        description: Text("Papers you bookmark will appear here for quick access.")
                    )
                } else {
                    List {
                        ForEach(filteredBookmarks) { bookmark in
                            NavigationLink(value: bookmark.paper) {
                                PaperRowView(paper: bookmark.paper)
                            }
                            .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                Button(role: .destructive) {
                                    bookmarksVM.deleteBookmarks([bookmark], in: modelContext)
                                } label: {
                                    Label("Delete", systemImage: "trash")
                                }
                            }
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Bookmarks")
            .navigationDestination(for: Paper.self) { paper in
                PaperDetailView(paper: paper)
            }
            .searchable(text: $bookmarksVM.searchText, prompt: "Filter bookmarks...")
            .toolbar {
                if !bookmarks.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) {
                        Text("\(bookmarks.count) saved")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    private var filteredBookmarks: [BookmarkedPaper] {
        guard !bookmarksVM.searchText.isEmpty else { return bookmarks }
        let query = bookmarksVM.searchText.lowercased()
        return bookmarks.filter {
            $0.title.lowercased().contains(query)
                || $0.venue.lowercased().contains(query)
                || $0.doi.lowercased().contains(query)
        }
    }
}
