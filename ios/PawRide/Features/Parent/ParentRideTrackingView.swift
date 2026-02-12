import AVKit
import SwiftUI

struct ParentRideTrackingView: View {
    @EnvironmentObject private var authStore: AuthStore
    let ride: Ride
    @StateObject private var realtime = RealtimeService()

    var body: some View {
        ScrollView {
            VStack(spacing: 14) {
                RoundedRectangle(cornerRadius: 16)
                    .fill(PawRideTheme.accent.opacity(0.25))
                    .frame(height: 180)
                    .overlay(
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Driver Location")
                                .font(.headline)
                            Text("Realtime map layer goes here")
                                .foregroundStyle(.secondary)
                        }
                        .padding()
                    )

                VStack(alignment: .leading, spacing: 8) {
                    Text("Ride Status: \(ride.status)")
                        .font(.headline)
                    Text("Pickup: \(ride.pickupAddress)")
                    Text("Dropoff: \(ride.dropoffAddress)")
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()
                .background(PawRideTheme.card, in: RoundedRectangle(cornerRadius: 14))

                Group {
                    if let streamURL = ride.cameraStreamURL, let url = URL(string: streamURL) {
                        VideoPlayer(player: AVPlayer(url: url))
                            .frame(height: 220)
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                    } else {
                        RoundedRectangle(cornerRadius: 14)
                            .fill(Color.black.opacity(0.1))
                            .frame(height: 220)
                            .overlay(Text("Live camera connects during active ride"))
                    }
                }

                Text("Realtime Event: \(realtime.lastEvent)")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding()
        }
        .background(PawRideTheme.background)
        .navigationTitle("Live Tracking")
        .task {
            guard let token = authStore.accessToken else { return }
            realtime.connectRideChannel(baseURL: APIClient.shared.baseURL, rideID: ride.id, accessToken: token)
        }
        .onDisappear {
            realtime.disconnect()
        }
    }
}
