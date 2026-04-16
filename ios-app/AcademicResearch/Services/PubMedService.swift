import Foundation

/// Client for NCBI PubMed E-utilities.
/// Clinical/biomedical literature, MeSH terms, Boolean queries.
struct PubMedService {
    private static let searchURL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    private static let fetchURL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    private static let summaryURL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    /// Search PubMed and return papers with basic metadata.
    static func searchPapers(
        query: String,
        numResults: Int = 10,
        year: String? = nil
    ) async throws -> [Paper] {
        // Step 1: Search for PMIDs
        var searchParams: [String: String] = [
            "db": "pubmed",
            "term": query,
            "retmax": String(min(numResults, 200)),
            "retmode": "json",
            "sort": "relevance"
        ]

        if let year, !year.isEmpty {
            if year.contains("-") {
                let parts = year.split(separator: "-", maxSplits: 1).map(String.init)
                if parts.count == 2, !parts[0].isEmpty, !parts[1].isEmpty {
                    searchParams["mindate"] = parts[0]
                    searchParams["maxdate"] = parts[1]
                    searchParams["datetype"] = "pdat"
                }
            } else {
                searchParams["mindate"] = year
                searchParams["maxdate"] = year
                searchParams["datetype"] = "pdat"
            }
        }

        let searchJSON = try await APIClient.shared.getRaw(url: searchURL, params: searchParams)
        guard let esearchResult = searchJSON["esearchresult"] as? [String: Any],
              let idList = esearchResult["idlist"] as? [String],
              !idList.isEmpty
        else {
            return []
        }

        // Step 2: Fetch summaries for the PMIDs
        let summaryParams: [String: String] = [
            "db": "pubmed",
            "id": idList.joined(separator: ","),
            "retmode": "json"
        ]

        let summaryJSON = try await APIClient.shared.getRaw(url: summaryURL, params: summaryParams)
        guard let result = summaryJSON["result"] as? [String: Any] else {
            return []
        }

        return idList.compactMap { pmid -> Paper? in
            guard let article = result[pmid] as? [String: Any] else { return nil }
            return formatArticle(article, pmid: pmid)
        }
    }

    // MARK: - Private Helpers

    private static func formatArticle(_ item: [String: Any], pmid: String) -> Paper? {
        let title = (item["title"] as? String ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "\\.$", with: "", options: .regularExpression)
        guard !title.isEmpty else { return nil }

        // Authors
        let rawAuthors = item["authors"] as? [[String: Any]] ?? []
        let authors = rawAuthors.compactMap { $0["name"] as? String }

        // Venue
        let venue = item["fulljournalname"] as? String
            ?? item["source"] as? String
            ?? ""

        // Year from pubdate
        let pubDate = item["pubdate"] as? String ?? ""
        let year = Int(String(pubDate.prefix(4)))

        // DOI from articleids
        var doi = ""
        if let articleIDs = item["articleids"] as? [[String: Any]] {
            for idInfo in articleIDs {
                if idInfo["idtype"] as? String == "doi" {
                    doi = idInfo["value"] as? String ?? ""
                    break
                }
            }
        }

        return Paper(
            title: title,
            authors: authors,
            year: year,
            venue: venue,
            citationCount: 0,
            abstract: "",  // PubMed summary endpoint doesn't include abstracts
            doi: doi,
            pmid: pmid,
            arxivID: "",
            isOpenAccess: false,
            openAccessURL: "",
            source: .pubMed,
            paperID: "",
            openAlexID: ""
        )
    }
}
