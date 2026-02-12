import SwiftUI

struct RoleSettingsPanel: View {
    @EnvironmentObject private var authStore: AuthStore

    var body: some View {
        List {
            Section("Active Role") {
                if let active = authStore.user?.activeRole {
                    Text(active.displayName)
                        .font(.headline)
                }
            }
            Section("Switch Role") {
                if let roles = authStore.user?.roles {
                    ForEach(roles) { role in
                        Button(role.displayName) {
                            Task { await authStore.switchRole(role) }
                        }
                    }
                }
            }
            Section("Account") {
                Button("Log Out", role: .destructive) {
                    authStore.logout()
                }
            }
        }
        .scrollContentBackground(.hidden)
        .background(PawRideTheme.background)
    }
}
