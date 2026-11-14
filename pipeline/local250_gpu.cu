// FP64 card-8 polar-chain march. No fast math. 128-distance launches bound
// individual GPU work on the display adapter and preserve CPU early-stop blocks.
#define PI 3.1415926535897932384626433832795
#define RAD (PI/180.0)
#define R 1737400.0
#define NAN __longlong_as_double(0x7ff8000000000000ULL)
__device__ double sample(const float* a,const double* p,double lat,double lon){
 double row,col;
 int nr=(int)p[1],nc=(int)p[2];
 if(p[0]==0){
  double rho=2*R*tan(PI/4+lat*RAD/2);
  col=(rho*sin(lon*RAD)-p[3])/p[4];row=(p[5]-rho*cos(lon*RAD))/p[6];
  if(!(row>=0&&row<=nr-1&&col>=0&&col<=nc-1))return NAN;
 }else{
  row=fmin(fmax(p[3]-lat*p[6],0.0),nr-1.0);
  double lm=fmod(lon,360.0);if(lm<0)lm+=360;
  col=p[4]+(lm-p[5])*p[6];
 }
 int ri=min((int)floor(row),nr-2),ci=(int)floor(col);
 if(p[0]==0)ci=min(ci,nc-2);
 double fy=row-ri,fx=col-ci;
 ci%=nc;if(ci<0)ci+=nc;int cj=(ci+1)%nc;
 double v=(1-fy)*((1-fx)*(double)a[ri*nc+ci]+fx*(double)a[ri*nc+cj])
          +fy*((1-fx)*(double)a[(ri+1)*nc+ci]+fx*(double)a[(ri+1)*nc+cj]);
 return v*p[7];
}
__device__ double chain(const unsigned long long* ptr,const double* pars,int nd,
 double lat,double lon,double s,int* source){
 for(int k=0;k<nd;k++)if(s<=pars[k*10+8]){
  double h=sample((const float*)ptr[k],pars+k*10,lat,lon);
  if(!isnan(h)){*source=k;return h;}
 }
 *source=-1;return NAN;
}
extern "C" __global__ void march_block(int n,int nd,const double* lat,const double* lon,
 const unsigned long long* ptr,const double* pars,const double* dist,const double* ct,const double* st,
 int ns,int first,double* best,int* active,int* missing,int* counts,double* used,double* ground){
 int q=blockDim.x*blockIdx.x+threadIdx.x;if(q>=n*720)return;
 int i=q/720,a=q%720,src;
 if(first>0&&!active[q])return;
 double la=lat[i]*RAD,lo=lon[i]*RAD,cl=cos(la),sl=sin(la),co=cos(lo),so=sin(lo);
 double ux=cl*co,uy=cl*so,uz=sl;
 double az=a*.5*RAD,ca=cos(az),sa=sin(az);
 double dx=-sl*co*ca-so*sa,dy=-sl*so*ca+co*sa,dz=cl*ca;
 double h0=chain(ptr,pars,nd,lat[i],lon[i],0,&src),ro=R+h0+2;
 if(a==0)ground[i]=h0;
 double b=first==0?-1e300:best[q];int miss=first==0?0:missing[q];
 double u[8];for(int k=0;k<nd;k++)u[k]=first==0?0:used[q*nd+k];
 int end=min(first+128,ns);
 counts[q]=(first==0?0:counts[q])+end-first;
 for(int k=first;k<end;k++){
  double x=ux*ct[k]+dx*st[k],y=uy*ct[k]+dy*st[k],z=uz*ct[k]+dz*st[k];
  double pla=asin(fmin(fmax(z,-1.0),1.0))/RAD,plo=atan2(y,x)/RAD;
  double h=chain(ptr,pars,nd,pla,plo,dist[k],&src);
  if(isnan(h)){miss++;continue;}
  u[src]=fmax(u[src],dist[k]);double rt=R+h;
  b=fmax(b,atan2(rt*ct[k]-ro,rt*st[k]));
 }
 best[q]=b;missing[q]=miss;
 for(int k=0;k<nd;k++)used[q*nd+k]=u[k];
 active[q]=end<ns && !(b>atan2((R+10800)*ct[end]-ro,(R+10800)*st[end]));
}
