import SwiftUI

struct DriverDocumentsView: View {
    var body: some View {
        NavigationStack {
            List {
                Section("Required Documents") {
                    Label("Driver License", systemImage: "checkmark.circle")
                    Label("Insurance", systemImage: "checkmark.circle")
                    Label("Vehicle Registration", systemImage: "checkmark.circle")
                    Label("Animal Handling Certificate", systemImage: "exclamationmark.circle")
                }
                Section("Camera Setup") {
                    Text("Use this screen to test camera angle and quality.")
                        .foregroundStyle(.secondary)
                }
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("Documents")
        }
    }
}
