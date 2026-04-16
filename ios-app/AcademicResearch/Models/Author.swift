import Foundation

/// Author profile from OpenAlex or Semantic Scholar.
struct Author: Identifiable, Codable, Hashable {
    var id: String { authorID }

    let authorID: String
    let name: String
    let affiliation: String
    let worksCount: Int
    let citationCount: Int
    let hIndex: Int?
    let source: PaperSource
}
