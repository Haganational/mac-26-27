# Mateo's channel (@MidMateoSandoval96)

Hardwood Bricks is the default YouTube channel for everything automatic. A video goes to Mateo's
channel only when Matthew asks for it: put it in `mateo/<slug>/` (video.mp4, optional thumb.jpg,
post.json with `"go": true`) on a branch and push. `.github/workflows/mateo.yml` uploads it with
`YT_REFRESH_TOKEN_MATEO` and writes the YouTube id back into post.json. Keep videos under 100 MB.
