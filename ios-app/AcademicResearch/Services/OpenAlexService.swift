import Foundation

/// Client for the OpenAlex API (https://api.openalex.org).
/// 250M+ works, no auth required. Highest throughput academic API.
struct OpenAlexService {
    private static let baseURL = "https://api.openalex.org"

    /// Search for academic works (papers, articles, preprints).
    static func searchWorks(
        query: String,
        numResults: Int = 10,
        year: String? = nil,
        openAccessOnly: Bool = false,
        sortBy: String = "relevance_score"
    ) async throws -> [Paper] {
        var params: [String: String] = [
            "search": query,
            "per_page": String(min(numResults, 200))
        ]

        if sortBy != "relevance_score" {
            params["sort"] = "\(sortBy):desc"
        }

        var filters: [String] = []
        if let year, !year.isEmpty {
            filters.append(contentsOf: yearFilters(year))
        }
        if openAccessOnly {
            filters.append("is_oa:true")
        }
        if !filters.isEmpty {
            params["filter"] = filters.joined(separator: ",")
        }

        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/works",
            params: params
        )

        guard let results = json["results"] as? [[String: Any]] else {
            return []
        }

        return results.compactMap { formatWork($0) }
    }

    /// Get details for a specific work by OpenAlex ID or DOI.
    static func getWork(id: String) async throws -> Paper? {
        var workID = id
        if workID.starts(with: "10.") {
            workID = "doi:\(workID)"
        }

        let encoded = workID.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? workID
        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/works/\(encoded)"
        )

        return formatWork(json)
    }

    /// Search for authors.
    static func searchAuthors(query: String, numResults: Int = 5) async throws -> [Author] {
        let params: [String: String] = [
            "search": query,
            "per_page": String(min(numResults, 50))
        ]

        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/authors",
            params: params
        )

        guard let results = json["results"] as? [[String: Any]] else {
            return []
        }

        return results.compactMap { formatAuthor($0) }
    }

    /// Get works by a specific author.
    static func getAuthorWorks(authorID: String, numResults: Int = 20) async throws -> [Paper] {
        let params: [String: String] = [
            "filter": "author.id:\(authorID)",
            "per_page": String(min(numResults, 200)),
            "sort": "cited_by_count:desc"
        ]

        let json = try await APIClient.shared.getRaw(
            url: "\(baseURL)/works",
            params: params
        )

        guard let results = json["results"] as? [[String: Any]] else {
            return []
        }

        return results.compactMap { formatWork($0) }
    }

    // MARK: - Private Helpers

    private static func yearFilters(_ year: String) -> [String] {
        var filters: [String] = []
        if year.contains("-") && !year.hasPrefix(">") && !year.hasPrefix("<") {
            let parts = year.split(separator: "-", maxSplits: 1).map(String.init)
            if parts.count == 2, !parts[0].isEmpty, !parts[1].isEmpty {
                filters.append("from_publication_date:\(parts[0])-01-01")
                filters.append("to_publication_date:\(parts[1])-12-31")
            } else if let first = parts.first, !first.isEmpty {
                filters.append("from_publication_date:\(first)-01-01")
            }
        } else if year.hasPrefix(">") {
            filters.append("from_publication_date:\(year.dropFirst())-01-01")
        } else if year.hasPrefix("<") {
            filters.append("to_publication_date:\(year.dropFirst())-12-31")
        } else {
            filters.append("publication_year:\(year)")
        }
        return filters
    }

    private static func formatWork(_ item: [String: Any]) -> Paper? {
        let title = item["title"] as? String ?? ""
        guard !title.isEmpty else { return nil }

        // Authors
        let authorships = item["authorships"] as? [[String: Any]] ?? []
        let authors = authorships.prefix(15).compactMap { authorship -> String? in
            let authorInfo = authorship["author"] as? [String: Any] ?? [:]
            return authorInfo["display_name"] as? String
        }

        // IDs
        let ids = item["ids"] as? [String: Any] ?? [:]
        let rawDOI = ids["doi"] as? String ?? ""
        let doi = rawDOI.replacingOccurrences(of: "https://doi.org/", with: "")
        let rawPMID = ids["pmid"] as? String ?? ""
        let pmid = rawPMID.replacingOccurrences(of: "https://pubmed.ncbi.nlm.nih.gov/", with: "")

        // Open access
        let oa = item["open_access"] as? [String: Any] ?? [:]
        let isOA = oa["is_oa"] as? Bool ?? false
        let oaURL = oa["oa_url"] as? String ?? ""

        // Venue
        let primaryLocation = item["primary_location"] as? [String: Any] ?? [:]
        let source = primaryLocation["source"] as? [String: Any] ?? [:]
        let venue = source["display_name"] as? String ?? ""

        // Abstract from inverted index
        var abstract = ""
        if let aii = item["abstract_inverted_index"] as? [String: [Int]], !aii.isEmpty {
            var positions: [Int: String] = [:]
            for (word, posList) in aii {
                for pos in posList {
                    positions[pos] = word
                }
            }
            abstract = positions.keys.sorted().compactMap { positions[$0] }.joined(separator: " ")
        }

        return Paper(
            title: title,
            authors: authors,
            year: item["publication_year"] as? Int,
            venue: venue,
            citationCount: item["cited_by_count"] as? Int ?? 0,
            abstract: abstract,
            doi: doi,
            pmid: pmid,
            arxivID: "",
            isOpenAccess: isOA,
            openAccessURL: oaURL,
            source: .openAlex,
            paperID: "",
            openAlexID: item["id"] as? String ?? ""
        )
    }

    private static func formatAuthor(_ item: [String: Any]) -> Author? {
        let name = item["display_name"] as? String ?? ""
        guard !name.isEmpty else { return nil }

        let lastKnown = item["last_known_institutions"] as? [[String: Any]] ?? []
        let affiliation = lastKnown.first?["display_name"] as? String ?? ""

        let summaryStats = item["summary_stats"] as? [String: Any] ?? [:]

        return Author(
            authorID: item["id"] as? String ?? "",
            name: name,
            affiliation: affiliation,
            worksCount: item["works_count"] as? Int ?? 0,
            citationCount: item["cited_by_count"] as? Int ?? 0,
            hIndex: summaryStats["h_index"] as? Int,
            source: .openAlex
        )
    }
}
