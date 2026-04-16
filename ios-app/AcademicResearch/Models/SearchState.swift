import Foundation

/// Tracks the state of an async search operation.
enum SearchState: Equatable {
    case idle
    case searching
    case loaded(count: Int)
    case error(String)

    var isSearching: Bool {
        if case .searching = self { return true }
        return false
    }
}

/// Filter options for paper searches.
struct SearchFilters: Equatable {
    var source: PaperSource? = nil
    var yearFrom: String = ""
    var yearTo: String = ""
    var openAccessOnly: Bool = false
    var sortBy: SortOption = .relevance

    var yearRange: String? {
        let from = yearFrom.trimmingCharacters(in: .whitespaces)
        let to = yearTo.trimmingCharacters(in: .whitespaces)
        if from.isEmpty && to.isEmpty { return nil }
        if from.isEmpty { return "-\(to)" }
        if to.isEmpty { return "\(from)-" }
        return "\(from)-\(to)"
    }
}

enum SortOption: String, CaseIterable, Identifiable {
    case relevance = "Relevance"
    case citations = "Citations"
    case date = "Date"

    var id: String { rawValue }

    var openAlexParam: String {
        switch self {
        case .relevance: return "relevance_score"
        case .citations: return "cited_by_count"
        case .date: return "publication_date"
        }
    }
}
