import SwiftUI

struct RoleRootView: View {
    @EnvironmentObject private var authStore: AuthStore

    var body: some View {
        Group {
            if authStore.needsRoleSelection, (authStore.user?.roles.count ?? 0) > 1 {
                RolePickerView()
            } else {
                switch authStore.user?.activeRole {
                case .dogParent:
                    ParentTabView()
                case .driver:
                    DriverTabView()
                case .admin:
                    AdminTabView()
                case .none:
                    Text("Loading...")
                }
            }
        }
        .background(PawRideTheme.background.ignoresSafeArea())
    }
}
