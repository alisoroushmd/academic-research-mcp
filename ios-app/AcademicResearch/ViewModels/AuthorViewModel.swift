import Foundation
import SwiftUI

/// Loads author details and their publications.
@Observable
@MainActor
final class AuthorViewModel {
    var query = ""
    var authors: [Author] = []
    var authorPapers: [Paper] = []
    var state: SearchState = .idle
    var isLoadingPapers = false

    func searchAuthors() {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        state = .searching
        authors = []

        Task {
            do {
                async let oalexAuthors = OpenAlexService.searchAuthors(query: trimmed, numResults: 10)
                async let s2Authors = SemanticScholarService.searchAuthors(query: trimmed, numResults: 10)

                let (oalex, s2) = try await (oalexAuthors, s2Authors)
                authors = oalex + s2
                state = .loaded(count: authors.count)
            } catch {
                state = .error(error.localizedDescription)
            }
        }
    }

    func loadAuthorPapers(author: Author) async {
        guard !author.authorID.isEmpty else { return }
        isLoadingPapers = true
        defer { isLoadingPapers = false }

        do {
            switch author.source {
            case .openAlex:
                authorPapers = try await OpenAlexService.getAuthorWorks(
                    authorID: author.authorID, numResults: 30
                )
            default:
                authorPapers = []
            }
        } catch {
            authorPapers = []
        }
    }
}
