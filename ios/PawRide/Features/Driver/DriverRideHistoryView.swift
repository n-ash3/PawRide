import SwiftUI

struct DriverRideHistoryView: View {
    var body: some View {
        NavigationStack {
            List {
                Text("Completed rides and ratings will appear here.")
                    .foregroundStyle(.secondary)
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("Ride History")
        }
    }
}
