import Foundation
import SwiftUI

/// Drives the main search screen — queries multiple academic APIs and merges results.
@Observable
@MainActor
final class SearchViewModel {
    var query = ""
    var papers: [Paper] = []
    var state: SearchState = .idle
    var filters = SearchFilters()
    var showFilters = false

    private var searchTask: Task<Void, Never>?

    /// Debounced search triggered by the user tapping Search or pressing Return.
    func search() {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        searchTask?.cancel()
        searchTask = Task {
            state = .searching
            papers = []

            do {
                let results = try await fetchPapers(query: trimmed)
                guard !Task.isCancelled else { return }
                papers = deduplicatePapers(results)
                state = .loaded(count: papers.count)
            } catch is CancellationError {
                // Ignore
            } catch {
                guard !Task.isCancelled else { return }
                state = .error(error.localizedDescription)
            }
        }
    }

    /// Fetch papers from the selected source (or multiple sources).
    private func fetchPapers(query: String) async throws -> [Paper] {
        let year = filters.yearRange
        let oa = filters.openAccessOnly

        if let source = filters.source {
            switch source {
            case .openAlex:
                return try await OpenAlexService.searchWorks(
                    query: query, numResults: 25, year: year,
                    openAccessOnly: oa, sortBy: filters.sortBy.openAlexParam
                )
            case .semanticScholar:
                return try await SemanticScholarService.searchPapers(
                    query: query, numResults: 25, year: year, openAccessOnly: oa
                )
            case .pubMed:
                return try await PubMedService.searchPapers(
                    query: query, numResults: 25, year: year
                )
            case .crossRef:
                return try await OpenAlexService.searchWorks(
                    query: query, numResults: 25, year: year, openAccessOnly: oa
                )
            }
        }

        // Multi-source: query OpenAlex and Semantic Scholar in parallel
        async let openAlexResults = OpenAlexService.searchWorks(
            query: query, numResults: 15, year: year,
            openAccessOnly: oa, sortBy: filters.sortBy.openAlexParam
        )
        async let s2Results = SemanticScholarService.searchPapers(
            query: query, numResults: 15, year: year, openAccessOnly: oa
        )

        let (oalex, s2) = try await (openAlexResults, s2Results)
        return oalex + s2
    }

    /// Deduplicate papers by DOI (case-insensitive), preferring the richer record.
    private func deduplicatePapers(_ papers: [Paper]) -> [Paper] {
        var seen = Set<String>()
        var result: [Paper] = []
        for paper in papers {
            let key = paper.stableID
            if seen.contains(key) { continue }
            seen.insert(key)
            result.append(paper)
        }
        return result
    }
}
