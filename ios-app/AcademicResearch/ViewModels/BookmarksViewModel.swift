import Foundation
import SwiftData
import SwiftUI

/// Manages the user's bookmarked papers using SwiftData.
@Observable
@MainActor
final class BookmarksViewModel {
    var searchText = ""

    /// Check if a paper is bookmarked.
    func isBookmarked(_ paper: Paper, in context: ModelContext) -> Bool {
        let stableID = paper.stableID
        let descriptor = FetchDescriptor<BookmarkedPaper>(
            predicate: #Predicate { $0.stableID == stableID }
        )
        return (try? context.fetchCount(descriptor)) ?? 0 > 0
    }

    /// Toggle bookmark state for a paper.
    func toggleBookmark(_ paper: Paper, in context: ModelContext) {
        let stableID = paper.stableID
        let descriptor = FetchDescriptor<BookmarkedPaper>(
            predicate: #Predicate { $0.stableID == stableID }
        )

        if let existing = try? context.fetch(descriptor).first {
            context.delete(existing)
        } else {
            let bookmark = BookmarkedPaper(from: paper)
            context.insert(bookmark)
        }

        try? context.save()
    }

    /// Delete specific bookmarks.
    func deleteBookmarks(_ bookmarks: [BookmarkedPaper], in context: ModelContext) {
        for bookmark in bookmarks {
            context.delete(bookmark)
        }
        try? context.save()
    }

    /// Update notes on a bookmark.
    func updateNotes(_ bookmark: BookmarkedPaper, notes: String, in context: ModelContext) {
        bookmark.notes = notes
        try? context.save()
    }
}
