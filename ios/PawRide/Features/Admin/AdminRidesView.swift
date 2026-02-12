import SwiftUI

struct AdminRidesView: View {
    var body: some View {
        NavigationStack {
            List {
                Text("Admin ride management list (filters, disputes, verification photos) goes here.")
                    .foregroundStyle(.secondary)
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("Rides")
        }
    }
}
