import Foundation

/// Executes tool calls from Claude by dispatching to the local API service layer.
/// This bridges the LLM's tool-use requests to the same academic APIs the MCP server uses.
struct ToolExecutor {

    /// Execute a tool call and return the result as a JSON-serializable dictionary.
    static func execute(_ call: ToolCall) async -> [String: Any] {
        do {
            switch call.name {
            case "smart_search":
                return try await executeSmartSearch(call.input)
            case "search_papers":
                return try await executeSearchPapers(call.input)
            case "find_paper":
                return try await executeFindPaper(call.input)
            case "get_paper_network":
                return try await executeGetPaperNetwork(call.input)
            case "recommend_papers":
                return try await executeRecommendPapers(call.input)
            case "search_authors":
                return try await executeSearchAuthors(call.input)
            case "get_author_works":
                return try await executeGetAuthorWorks(call.input)
            case "open_access":
                return try await executeOpenAccess(call.input)
            default:
                return ["error": "Unknown tool: \(call.name)"]
            }
        } catch {
            return ["error": error.localizedDescription]
        }
    }

    // MARK: - Tool Implementations

    private static func executeSmartSearch(_ input: [String: Any]) async throws -> [String: Any] {
        let query = input["query"] as? String ?? ""
        let numResults = input["num_results"] as? Int ?? 10
        let year = input["year"] as? String
        let oaOnly = input["open_access_only"] as? Bool ?? false

        async let oalexResults = OpenAlexService.searchWorks(
            query: query, numResults: numResults, year: year, openAccessOnly: oaOnly
        )
        async let s2Results = SemanticScholarService.searchPapers(
            query: query, numResults: numResults, year: year, openAccessOnly: oaOnly
        )

        let (oalex, s2) = try await (oalexResults, s2Results)
        let merged = deduplicateAndSerialize(oalex + s2)

        return [
            "total": merged.count,
            "papers": merged
        ]
    }

    private static func executeSearchPapers(_ input: [String: Any]) async throws -> [String: Any] {
        let query = input["query"] as? String ?? ""
        let source = input["source"] as? String ?? "openalex"
        let numResults = input["num_results"] as? Int ?? 10
        let year = input["year"] as? String
        let oaOnly = input["open_access_only"] as? Bool ?? false

        let papers: [Paper]
        switch source {
        case "s2":
            papers = try await SemanticScholarService.searchPapers(
                query: query, numResults: numResults, year: year, openAccessOnly: oaOnly
            )
        case "pubmed":
            papers = try await PubMedService.searchPapers(
                query: query, numResults: numResults, year: year
            )
        default:
            papers = try await OpenAlexService.searchWorks(
                query: query, numResults: numResults, year: year, openAccessOnly: oaOnly
            )
        }

        return [
            "source": source,
            "total": papers.count,
            "papers": papers.map { serializePaper($0) }
        ]
    }

    private static func executeFindPaper(_ input: [String: Any]) async throws -> [String: Any] {
        let identifier = input["identifier"] as? String ?? ""

        // Try Semantic Scholar first (handles DOI, PMID, arXiv, S2 ID)
        if let paper = try? await SemanticScholarService.getPaperDetails(paperID: identifier) {
            return serializePaper(paper)
        }

        // Fallback to OpenAlex
        if let paper = try? await OpenAlexService.getWork(id: identifier) {
            return serializePaper(paper)
        }

        // Last resort: search by title
        let results = try await OpenAlexService.searchWorks(query: identifier, numResults: 1)
        if let paper = results.first {
            return serializePaper(paper)
        }

        return ["error": "Paper not found for identifier: \(identifier)"]
    }

    private static func executeGetPaperNetwork(_ input: [String: Any]) async throws -> [String: Any] {
        let paperID = input["paper_id"] as? String ?? ""
        let direction = input["direction"] as? String ?? "both"
        let numResults = input["num_results"] as? Int ?? 10

        var result: [String: Any] = ["paper_id": paperID]

        if direction == "citations" || direction == "both" {
            let citations = try await SemanticScholarService.getCitations(
                paperID: paperID, numResults: numResults
            )
            result["citations"] = [
                "count": citations.count,
                "papers": citations.map { serializePaper($0) }
            ]
        }

        if direction == "references" || direction == "both" {
            let references = try await SemanticScholarService.getReferences(
                paperID: paperID, numResults: numResults
            )
            result["references"] = [
                "count": references.count,
                "papers": references.map { serializePaper($0) }
            ]
        }

        return result
    }

    private static func executeRecommendPapers(_ input: [String: Any]) async throws -> [String: Any] {
        let paperID = input["paper_id"] as? String ?? ""
        let numResults = input["num_results"] as? Int ?? 5

        let recs = try await SemanticScholarService.getRecommendations(
            paperID: paperID, numResults: numResults
        )

        return [
            "paper_id": paperID,
            "recommendations": recs.map { serializePaper($0) }
        ]
    }

    private static func executeSearchAuthors(_ input: [String: Any]) async throws -> [String: Any] {
        let query = input["query"] as? String ?? ""
        let numResults = input["num_results"] as? Int ?? 5

        async let oalexAuthors = OpenAlexService.searchAuthors(query: query, numResults: numResults)
        async let s2Authors = SemanticScholarService.searchAuthors(query: query, numResults: numResults)

        let (oalex, s2) = try await (oalexAuthors, s2Authors)

        return [
            "total": oalex.count + s2.count,
            "authors": (oalex + s2).map { serializeAuthor($0) }
        ]
    }

    private static func executeGetAuthorWorks(_ input: [String: Any]) async throws -> [String: Any] {
        let authorID = input["author_id"] as? String ?? ""
        let numResults = input["num_results"] as? Int ?? 20

        let works = try await OpenAlexService.getAuthorWorks(
            authorID: authorID, numResults: numResults
        )

        return [
            "author_id": authorID,
            "total": works.count,
            "papers": works.map { serializePaper($0) }
        ]
    }

    private static func executeOpenAccess(_ input: [String: Any]) async throws -> [String: Any] {
        let doi = input["doi"] as? String ?? ""

        // Try to resolve via OpenAlex
        if let paper = try? await OpenAlexService.getWork(id: doi), paper.isOpenAccess {
            return [
                "doi": doi,
                "is_open_access": true,
                "url": paper.openAccessURL
            ]
        }

        return [
            "doi": doi,
            "is_open_access": false,
            "url": ""
        ]
    }

    // MARK: - Serialization

    private static func serializePaper(_ p: Paper) -> [String: Any] {
        var dict: [String: Any] = [
            "title": p.title,
            "authors": p.authors,
            "year": p.year as Any,
            "cited_by": p.citationCount,
            "doi": p.doi,
            "source": p.source.rawValue
        ]
        if !p.abstract.isEmpty {
            let snippet = p.abstract.count > 300
                ? String(p.abstract.prefix(300)) + "..."
                : p.abstract
            dict["abstract_snippet"] = snippet
        }
        if !p.venue.isEmpty { dict["venue"] = p.venue }
        if !p.pmid.isEmpty { dict["pmid"] = p.pmid }
        if !p.arxivID.isEmpty { dict["arxiv_id"] = p.arxivID }
        if p.isOpenAccess { dict["open_access_url"] = p.openAccessURL }
        return dict
    }

    private static func serializeAuthor(_ a: Author) -> [String: Any] {
        var dict: [String: Any] = [
            "name": a.name,
            "id": a.authorID,
            "works_count": a.worksCount,
            "citation_count": a.citationCount,
            "source": a.source.rawValue
        ]
        if !a.affiliation.isEmpty { dict["affiliation"] = a.affiliation }
        if let h = a.hIndex { dict["h_index"] = h }
        return dict
    }

    private static func deduplicateAndSerialize(_ papers: [Paper]) -> [[String: Any]] {
        var seen = Set<String>()
        var result: [[String: Any]] = []
        for paper in papers {
            let key = paper.stableID
            if seen.contains(key) { continue }
            seen.insert(key)
            result.append(serializePaper(paper))
        }
        return result
    }
}
