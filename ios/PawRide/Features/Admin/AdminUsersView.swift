import SwiftUI

struct AdminUsersView: View {
    var body: some View {
        NavigationStack {
            List {
                Text("User management, dog oversight, and driver approval workflows live here.")
                    .foregroundStyle(.secondary)
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("Users")
        }
    }
}
