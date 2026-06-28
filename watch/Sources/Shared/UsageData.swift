import Foundation

struct UsageData {
    var fiveUsed: Int
    var weekUsed: Int
    var updatedEpoch: Int

    static let placeholder = UsageData(fiveUsed: 60, weekUsed: 85,
                                       updatedEpoch: Int(Date().timeIntervalSince1970))

    var relativeUpdated: String {
        let m = max(0, Int(Date().timeIntervalSince1970) - updatedEpoch) / 60
        if m < 1 { return "刚刚" }
        if m < 60 { return "\(m) 分钟前" }
        return "\(m / 60) 小时前"
    }
}

private struct UsageDTO: Decodable {
    struct Block: Decodable { let used_pct: Int? }
    let five_hour: Block?
    let seven_day: Block?
    let updated_epoch: Int?
}

func fetchUsage() async -> UsageData? {
    // cache-buster query so GitHub's CDN can't serve a stale copy
    let busted = gistURL + (gistURL.contains("?") ? "&" : "?")
        + "t=\(Int(Date().timeIntervalSince1970))"
    guard let url = URL(string: busted) else { return nil }
    var req = URLRequest(url: url)
    req.cachePolicy = .reloadIgnoringLocalCacheData
    req.timeoutInterval = 20
    do {
        let (data, _) = try await URLSession.shared.data(for: req)
        let dto = try JSONDecoder().decode(UsageDTO.self, from: data)
        return UsageData(fiveUsed: dto.five_hour?.used_pct ?? 0,
                         weekUsed: dto.seven_day?.used_pct ?? 0,
                         updatedEpoch: dto.updated_epoch ?? Int(Date().timeIntervalSince1970))
    } catch {
        return nil
    }
}
