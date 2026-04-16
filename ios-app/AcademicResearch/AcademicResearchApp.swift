import SwiftUI
import SwiftData

@main
struct AcademicResearchApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .modelContainer(for: BookmarkedPaper.self)
    }
}
