import SwiftUI

/// Sheet for configuring search filters.
struct FilterSheet: View {
    @Binding var filters: SearchFilters
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("Source") {
                    Picker("API Source", selection: $filters.source) {
                        Text("All Sources").tag(nil as PaperSource?)
                        ForEach(PaperSource.allCases, id: \.self) { source in
                            Text(source.rawValue).tag(source as PaperSource?)
                        }
                    }
                    .pickerStyle(.menu)
                }

                Section("Year Range") {
                    HStack {
                        TextField("From", text: $filters.yearFrom)
                            .keyboardType(.numberPad)
                        Text("—")
                            .foregroundStyle(.secondary)
                        TextField("To", text: $filters.yearTo)
                            .keyboardType(.numberPad)
                    }
                }

                Section("Options") {
                    Toggle("Open Access Only", isOn: $filters.openAccessOnly)

                    Picker("Sort By", selection: $filters.sortBy) {
                        ForEach(SortOption.allCases) { option in
                            Text(option.rawValue).tag(option)
                        }
                    }
                }

                Section {
                    Button("Reset Filters") {
                        filters = SearchFilters()
                    }
                    .foregroundStyle(.red)
                }
            }
            .navigationTitle("Search Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .presentationDetents([.medium])
    }
}
