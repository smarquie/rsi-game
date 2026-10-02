"""Assumption-3 symmetric model, distinct from the finite-dither engine."""
import numpy as np
from scipy.optimize import brentq
from .fast import best_response
from .world import kappa

def symmetric_maps(n=5,b=1.,c=-.3,gamma=1.,alpha=.3,xstar=.6,beta=.7):
    B=n*gamma*kappa(xstar)
    def Q(x):return float(-np.expm1(-(B/gamma-kappa(x))/(n-1)))
    def price(q):return (b+alpha+2*c*q)*(1-q)/gamma
    def X(p):return best_response(b,c,0,1,gamma,p,0,1-1e-6)
    def F(x):return (1-beta)*x+beta*X(price(Q(x)))
    x=brentq(lambda x:X(price(Q(x)))-x,0,xstar)
    q=Q(x);p=price(q);Xp=(gamma/(1-x))/(2*c-p*gamma/(1-x)**2);pp=(2*c*(1-q)-(b+alpha+2*c*q))/gamma;qp=-(1-q)/((n-1)*(1-x));L=abs(Xp*pp*qp)
    return dict(target=x,free=q,gap=q-x,price=p,feedback=L,critical_beta=2/(1+L),derivative=1-beta*(1+L),numerical_derivative=(F(x+1e-6)-F(x-1e-6))/2e-6)
