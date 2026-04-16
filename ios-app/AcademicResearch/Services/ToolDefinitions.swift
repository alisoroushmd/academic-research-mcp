import Foundation

/// Tool definitions matching the MCP server's tools, formatted for the Anthropic API.
enum ToolDefinitions {

    static let all: [[String: Any]] = [
        smartSearch,
        searchPapers,
        findPaper,
        getPaperNetwork,
        recommendPapers,
        searchAuthors,
        getAuthorWorks,
        openAccess
    ]

    static let smartSearch: [String: Any] = [
        "name": "smart_search",
        "description": "Multi-source academic paper search with deduplication. Searches OpenAlex and Semantic Scholar in parallel and merges results. This is the recommended default search tool.",
        "input_schema": [
            "type": "object",
            "properties": [
                "query": [
                    "type": "string",
                    "description": "Search query (topic, keywords, paper title, etc.)"
                ],
                "num_results": [
                    "type": "integer",
                    "description": "Number of results per source (default 10, max 25)"
                ],
                "year": [
                    "type": "string",
                    "description": "Year filter: '2020', '2020-2025', '>2022'"
                ],
                "open_access_only": [
                    "type": "boolean",
                    "description": "Only return open-access papers"
                ]
            ],
            "required": ["query"]
        ]
    ]

    static let searchPapers: [String: Any] = [
        "name": "search_papers",
        "description": "Search a specific academic source. Use 'source' to pick: openalex, s2 (Semantic Scholar), or pubmed. PubMed supports MeSH terms and Boolean syntax.",
        "input_schema": [
            "type": "object",
            "properties": [
                "query": [
                    "type": "string",
                    "description": "Search query"
                ],
                "source": [
                    "type": "string",
                    "enum": ["openalex", "s2", "pubmed"],
                    "description": "Which API to search"
                ],
                "num_results": [
                    "type": "integer",
                    "description": "Number of results (default 10)"
                ],
                "year": [
                    "type": "string",
                    "description": "Year filter"
                ],
                "open_access_only": [
                    "type": "boolean",
                    "description": "Only return open-access papers"
                ]
            ],
            "required": ["query", "source"]
        ]
    ]

    static let findPaper: [String: Any] = [
        "name": "find_paper",
        "description": "Universal paper resolver. Accepts any identifier: DOI (e.g. '10.1038/s41591-023-02437-x'), PMID, arXiv ID, Semantic Scholar ID, or a title string. Returns full paper details.",
        "input_schema": [
            "type": "object",
            "properties": [
                "identifier": [
                    "type": "string",
                    "description": "DOI, PMID, arXiv ID, S2 paper ID, or title"
                ]
            ],
            "required": ["identifier"]
        ]
    ]

    static let getPaperNetwork: [String: Any] = [
        "name": "get_paper_network",
        "description": "Get the citation network for a paper: forward citations (who cited this), backward references (what this cites), or both. Uses Semantic Scholar.",
        "input_schema": [
            "type": "object",
            "properties": [
                "paper_id": [
                    "type": "string",
                    "description": "Paper identifier (DOI, S2 ID, PMID with prefix)"
                ],
                "direction": [
                    "type": "string",
                    "enum": ["citations", "references", "both"],
                    "description": "Which direction to traverse (default: both)"
                ],
                "num_results": [
                    "type": "integer",
                    "description": "Max papers per direction (default 10)"
                ]
            ],
            "required": ["paper_id"]
        ]
    ]

    static let recommendPapers: [String: Any] = [
        "name": "recommend_papers",
        "description": "Get paper recommendations: 'papers like this one'. Powered by Semantic Scholar.",
        "input_schema": [
            "type": "object",
            "properties": [
                "paper_id": [
                    "type": "string",
                    "description": "Paper identifier (DOI or S2 ID)"
                ],
                "num_results": [
                    "type": "integer",
                    "description": "Number of recommendations (default 5)"
                ]
            ],
            "required": ["paper_id"]
        ]
    ]

    static let searchAuthors: [String: Any] = [
        "name": "search_authors",
        "description": "Search for researchers by name. Returns profiles with affiliation, works count, citation count, and h-index.",
        "input_schema": [
            "type": "object",
            "properties": [
                "query": [
                    "type": "string",
                    "description": "Author name to search"
                ],
                "num_results": [
                    "type": "integer",
                    "description": "Number of results (default 5)"
                ]
            ],
            "required": ["query"]
        ]
    ]

    static let getAuthorWorks: [String: Any] = [
        "name": "get_author_works",
        "description": "Get publications by a specific author. Requires an OpenAlex author ID.",
        "input_schema": [
            "type": "object",
            "properties": [
                "author_id": [
                    "type": "string",
                    "description": "OpenAlex author ID (e.g. 'https://openalex.org/A...')"
                ],
                "num_results": [
                    "type": "integer",
                    "description": "Number of works to return (default 20)"
                ]
            ],
            "required": ["author_id"]
        ]
    ]

    static let openAccess: [String: Any] = [
        "name": "open_access",
        "description": "Find legal open-access PDF links for papers by DOI.",
        "input_schema": [
            "type": "object",
            "properties": [
                "doi": [
                    "type": "string",
                    "description": "DOI of the paper"
                ]
            ],
            "required": ["doi"]
        ]
    ]
}
