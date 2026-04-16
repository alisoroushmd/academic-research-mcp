import Foundation

/// Client for the Semantic Scholar Academic Graph API.
/// Citation graphs, author metrics, paper recommendations.
struct SemanticScholarService {
    private static let baseURL = "https://api.semanticscholar.org/graph/v1"

    private static let defaultFields =
        "title,authors,year,citationCount,abstract,externalIds,venue," +
        "openAccessPdf,publicationTypes,journal,influentialCitationCount"

    /// Search for papers.
    static func searchPapers(
        query: String,
        numResults: Int = 10,
        year: String? = nil,
        openAccessOnly: Bool = false
    ) async throws -> [Paper] {
        var params: [String: String] = [
            "query": query,
            "limit": String(min(numResults, 100)),
            "fields": defaultFields
        ]

        if let year, !year.isEmpty {
            params["year"] = year
        }
        if openAccessOnly {
            params["openAccessPdf"] = ""
        }

        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/paper/search",
            params: params
        )

        guard let data = json["data"] as? [[String: Any]] else {
            return []
        }

        return data.compactMap { formatPaper($0) }
    }

    /// Get detailed information about a specific paper.
    static func getPaperDetails(paperID: String) async throws -> Paper? {
        let encoded = paperID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? paperID
        let fields = defaultFields + ",tldr"

        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/paper/\(encoded)",
            params: ["fields": fields]
        )

        return formatPaper(json)
    }

    /// Get papers that cite a given paper.
    static func getCitations(paperID: String, numResults: Int = 20) async throws -> [Paper] {
        let encoded = paperID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? paperID
        let params: [String: String] = [
            "limit": String(min(numResults, 100)),
            "fields": "title,authors,year,citationCount,venue,externalIds"
        ]

        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/paper/\(encoded)/citations",
            params: params
        )

        guard let data = json["data"] as? [[String: Any]] else {
            return []
        }

        return data.compactMap { item -> Paper? in
            guard let citing = item["citingPaper"] as? [String: Any] else { return nil }
            return formatPaper(citing)
        }
    }

    /// Get papers referenced by a given paper.
    static func getReferences(paperID: String, numResults: Int = 20) async throws -> [Paper] {
        let encoded = paperID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? paperID
        let params: [String: String] = [
            "limit": String(min(numResults, 100)),
            "fields": "title,authors,year,citationCount,venue,externalIds"
        ]

        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/paper/\(encoded)/references",
            params: params
        )

        guard let data = json["data"] as? [[String: Any]] else {
            return []
        }

        return data.compactMap { item -> Paper? in
            guard let cited = item["citedPaper"] as? [String: Any] else { return nil }
            return formatPaper(cited)
        }
    }

    /// Get recommended papers similar to a given paper.
    static func getRecommendations(paperID: String, numResults: Int = 10) async throws -> [Paper] {
        let encoded = paperID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? paperID
        let params: [String: String] = [
            "limit": String(min(numResults, 100)),
            "fields": defaultFields
        ]

        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/recommendations/v1/papers/forpaper/\(encoded)",
            params: params
        )

        guard let papers = json["recommendedPapers"] as? [[String: Any]] else {
            return []
        }

        return papers.compactMap { formatPaper($0) }
    }

    /// Search for authors.
    static func searchAuthors(query: String, numResults: Int = 5) async throws -> [Author] {
        let params: [String: String] = [
            "query": query,
            "limit": String(min(numResults, 100)),
            "fields": "name,affiliations,paperCount,citationCount,hIndex"
        ]

        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/author/search",
            params: params
        )

        guard let data = json["data"] as? [[String: Any]] else {
            return []
        }

        return data.compactMap { formatAuthor($0) }
    }

    // MARK: - Private Helpers

    private static func formatPaper(_ item: [String: Any]) -> Paper? {
        let title = item["title"] as? String ?? ""
        guard !title.isEmpty else { return nil }

        let extIDs = item["externalIds"] as? [String: Any] ?? [:]
        let rawAuthors = item["authors"] as? [[String: Any]] ?? []
        let journal = item["journal"] as? [String: Any] ?? [:]
        let oaPdf = item["openAccessPdf"] as? [String: Any] ?? [:]

        let authors = rawAuthors.prefix(10).compactMap { $0["name"] as? String }
        let venue = (item["venue"] as? String) ?? (journal["name"] as? String) ?? ""
        let oaURL = oaPdf["url"] as? String ?? ""

        return Paper(
            title: title,
            authors: authors,
            year: item["year"] as? Int,
            venue: venue,
            citationCount: item["citationCount"] as? Int ?? 0,
            abstract: item["abstract"] as? String ?? "",
            doi: extIDs["DOI"] as? String ?? "",
            pmid: extIDs["PubMed"] as? String ?? "",
            arxivID: extIDs["ArXiv"] as? String ?? "",
            isOpenAccess: !oaURL.isEmpty,
            openAccessURL: oaURL,
            source: .semanticScholar,
            paperID: item["paperId"] as? String ?? "",
            openAlexID: ""
        )
    }

    private static func formatAuthor(_ item: [String: Any]) -> Author? {
        let name = item["name"] as? String ?? ""
        guard !name.isEmpty else { return nil }

        let affiliations = item["affiliations"] as? [String] ?? []

        return Author(
            authorID: item["authorId"] as? String ?? "",
            name: name,
            affiliation: affiliations.first ?? "",
            worksCount: item["paperCount"] as? Int ?? 0,
            citationCount: item["citationCount"] as? Int ?? 0,
            hIndex: item["hIndex"] as? Int,
            source: .semanticScholar
        )
    }
}
