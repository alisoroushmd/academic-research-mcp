import Foundation
import SwiftUI

/// Loads citation network and recommendations for a given paper.
@Observable
@MainActor
final class PaperDetailViewModel {
    let paper: Paper

    var citations: [Paper] = []
    var references: [Paper] = []
    var recommendations: [Paper] = []

    var isLoadingCitations = false
    var isLoadingReferences = false
    var isLoadingRecommendations = false
    var errorMessage: String?

    init(paper: Paper) {
        self.paper = paper
    }

    /// Resolve the Semantic Scholar paper ID for this paper.
    private var s2PaperID: String {
        if !paper.paperID.isEmpty { return paper.paperID }
        if !paper.doi.isEmpty { return paper.doi }
        return ""
    }

    /// Load citations (papers that cite this one).
    func loadCitations() async {
        let id = s2PaperID
        guard !id.isEmpty, citations.isEmpty else { return }
        isLoadingCitations = true
        defer { isLoadingCitations = false }

        do {
            citations = try await SemanticScholarService.getCitations(paperID: id, numResults: 20)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Load references (papers this one cites).
    func loadReferences() async {
        let id = s2PaperID
        guard !id.isEmpty, references.isEmpty else { return }
        isLoadingReferences = true
        defer { isLoadingReferences = false }

        do {
            references = try await SemanticScholarService.getReferences(paperID: id, numResults: 20)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Load recommended papers.
    func loadRecommendations() async {
        let id = s2PaperID
        guard !id.isEmpty, recommendations.isEmpty else { return }
        isLoadingRecommendations = true
        defer { isLoadingRecommendations = false }

        do {
            recommendations = try await SemanticScholarService.getRecommendations(
                paperID: id, numResults: 10
            )
        } catch {
            // Recommendations may not be available for all papers — non-critical
        }
    }
}
