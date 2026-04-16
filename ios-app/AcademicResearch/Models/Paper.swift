import Foundation
import SwiftData

/// Unified paper model that normalizes results from OpenAlex, Semantic Scholar, and PubMed.
struct Paper: Identifiable, Codable, Hashable {
    var id: String { stableID }

    let title: String
    let authors: [String]
    let year: Int?
    let venue: String
    let citationCount: Int
    let abstract: String
    let doi: String
    let pmid: String
    let arxivID: String
    let isOpenAccess: Bool
    let openAccessURL: String
    let source: PaperSource
    let paperID: String       // Semantic Scholar paper ID
    let openAlexID: String

    /// Stable identifier across sources — prefers DOI, then PMID, then source-specific ID.
    var stableID: String {
        if !doi.isEmpty { return "doi:\(doi.lowercased())" }
        if !pmid.isEmpty { return "pmid:\(pmid)" }
        if !paperID.isEmpty { return "s2:\(paperID)" }
        if !openAlexID.isEmpty { return "oalex:\(openAlexID)" }
        return "title:\(title.lowercased().prefix(80))"
    }

    var doiURL: URL? {
        guard !doi.isEmpty else { return nil }
        return URL(string: "https://doi.org/\(doi)")
    }

    var openAccessPDFURL: URL? {
        guard !openAccessURL.isEmpty else { return nil }
        return URL(string: openAccessURL)
    }

    var authorsDisplay: String {
        switch authors.count {
        case 0: return "Unknown authors"
        case 1: return authors[0]
        case 2: return "\(authors[0]) & \(authors[1])"
        case 3: return "\(authors[0]), \(authors[1]) & \(authors[2])"
        default: return "\(authors[0]), \(authors[1]) et al."
        }
    }

    var abstractSnippet: String {
        guard !abstract.isEmpty else { return "" }
        if abstract.count <= 200 { return abstract }
        let truncated = String(abstract.prefix(200))
        if let lastSpace = truncated.lastIndex(of: " ") {
            return String(truncated[..<lastSpace]) + "..."
        }
        return truncated + "..."
    }
}

enum PaperSource: String, Codable, CaseIterable {
    case openAlex = "OpenAlex"
    case semanticScholar = "Semantic Scholar"
    case pubMed = "PubMed"
    case crossRef = "CrossRef"
}

// MARK: - SwiftData Bookmark Model

@Model
final class BookmarkedPaper {
    @Attribute(.unique) var stableID: String
    var title: String
    var authorsJSON: String
    var year: Int?
    var venue: String
    var citationCount: Int
    var abstract: String
    var doi: String
    var pmid: String
    var arxivID: String
    var isOpenAccess: Bool
    var openAccessURL: String
    var sourceRaw: String
    var paperID: String
    var openAlexID: String
    var bookmarkedAt: Date
    var notes: String

    init(from paper: Paper, notes: String = "") {
        self.stableID = paper.stableID
        self.title = paper.title
        self.authorsJSON = (try? JSONEncoder().encode(paper.authors))
            .flatMap { String(data: $0, encoding: .utf8) } ?? "[]"
        self.year = paper.year
        self.venue = paper.venue
        self.citationCount = paper.citationCount
        self.abstract = paper.abstract
        self.doi = paper.doi
        self.pmid = paper.pmid
        self.arxivID = paper.arxivID
        self.isOpenAccess = paper.isOpenAccess
        self.openAccessURL = paper.openAccessURL
        self.sourceRaw = paper.source.rawValue
        self.paperID = paper.paperID
        self.openAlexID = paper.openAlexID
        self.bookmarkedAt = Date()
        self.notes = notes
    }

    var paper: Paper {
        let authors = (try? JSONDecoder().decode([String].self,
            from: Data(authorsJSON.utf8))) ?? []
        return Paper(
            title: title,
            authors: authors,
            year: year,
            venue: venue,
            citationCount: citationCount,
            abstract: abstract,
            doi: doi,
            pmid: pmid,
            arxivID: arxivID,
            isOpenAccess: isOpenAccess,
            openAccessURL: openAccessURL,
            source: PaperSource(rawValue: sourceRaw) ?? .openAlex,
            paperID: paperID,
            openAlexID: openAlexID
        )
    }
}
